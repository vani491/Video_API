import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import HTTPException
from core.config import config

class VideoValidator:
    """Validates video files and extracts metadata"""
    
    @staticmethod
    def validate_file_extension(filename: str) -> bool:
        """Check if file has allowed extension"""
        file_path = Path(filename)
        return file_path.suffix.lower() in config.ALLOWED_EXTENSIONS
    
    @staticmethod
    def validate_file_size(file_size: int) -> bool:
        """Check if file size is within limits"""
        return file_size <= config.MAX_FILE_SIZE
    
    @staticmethod
    async def get_video_info(file_path: Path) -> Dict[str, Any]:
        """
        Get video metadata using ffprobe
        Returns duration, width, height, etc.
        """
        try:
            cmd = [
                '/usr/bin/ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(file_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid video file: {result.stderr}"
                )
            
            data = json.loads(result.stdout)
            
            # Find video stream
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                raise HTTPException(
                    status_code=400,
                    detail="No video stream found in file"
                )
            
            # Extract information
            duration = float(data['format'].get('duration', 0))
            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            
            return {
                'duration': duration,
                'width': width,
                'height': height,
                'codec': video_stream.get('codec_name'),
                'format': data['format'].get('format_name'),
                'size': int(data['format'].get('size', 0))
            }
            
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=400,
                detail="Video analysis timed out"
            )
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Failed to parse video information"
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error analyzing video: {str(e)}"
            )
    
    @staticmethod
    async def validate_video_duration(file_path: Path) -> bool:
        """Check if video duration is within limits"""
        try:
            info = await VideoValidator.get_video_info(file_path)
            duration = info['duration']
            
            return (config.MIN_VIDEO_DURATION <= duration <= config.MAX_VIDEO_DURATION)
        except:
            return False
    
    @staticmethod
    async def full_video_validation(file_path: Path, original_filename: str) -> Dict[str, Any]:
        """
        Perform complete video validation
        Returns video info if valid, raises HTTPException if invalid
        """
        # Check file extension
        if not VideoValidator.validate_file_extension(original_filename):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(config.ALLOWED_EXTENSIONS)}"
            )
        
        # Check file exists
        if not file_path.exists():
            raise HTTPException(
                status_code=400,
                detail="File not found"
            )
        
        # Check file size
        file_size = file_path.stat().st_size
        if not VideoValidator.validate_file_size(file_size):
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {config.MAX_FILE_SIZE / (1024*1024):.1f}MB"
            )
        
        # Get video info and validate duration
        video_info = await VideoValidator.get_video_info(file_path)
        
        if not (config.MIN_VIDEO_DURATION <= video_info['duration'] <= config.MAX_VIDEO_DURATION):
            raise HTTPException(
                status_code=400,
                detail=f"Video duration must be between {config.MIN_VIDEO_DURATION} and {config.MAX_VIDEO_DURATION} seconds"
            )
        
        return video_info 
