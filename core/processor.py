import asyncio
import subprocess
import uuid


from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException
from core.config import config
from core.storage import file_storage
from utils.validation import VideoValidator
from middleware.processing_lock import processing_lock




class VideoProcessor:
    """Handles video processing operations using FFmpeg"""
    
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
    
    def create_job(self, original_filename: str, upload_filename: str) -> str:
        """Create a new processing job"""
        job_id = str(uuid.uuid4())[:8]
        
        self.jobs[job_id] = {
            "id": job_id,
            "original_filename": original_filename,
            "upload_filename": upload_filename,
            "output_filename": None,
            "status": "created",
            "progress": 0,
            "created_at": datetime.now(),
            "started_at": None,
            "completed_at": None,
            "error": None,
            "file_info": None
        }
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status by ID"""
        return self.jobs.get(job_id)
    
    def update_job_status(self, job_id: str, status: str, **kwargs):
        """Update job status and additional fields"""
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = status
            self.jobs[job_id].update(kwargs)
    
    async def process_video(self, job_id: str) -> Dict[str, Any]:
        """
        Process video with speed adjustment
        Returns job status after processing
        """
        try:
            # Check if job exists
            if job_id not in self.jobs:
                raise HTTPException(status_code=404, detail="Job not found")
            
            job = self.jobs[job_id]
            
            # Try to acquire processing lock
            if not await processing_lock.acquire(job_id):
                self.update_job_status(job_id, "rejected", error="Another video is currently being processed")
                raise HTTPException(status_code=429, detail="Server busy. Another video is being processed.")
            
            try:
                # Update job status
                self.update_job_status(job_id, "validating", started_at=datetime.now())
                
                # Get file paths
                input_path = file_storage.get_upload_file_path(job["upload_filename"])
                
                # Validate video file
                video_info = await VideoValidator.full_video_validation(input_path, job["original_filename"])
                self.update_job_status(job_id, "validated", file_info=video_info, progress=20)
                
                # Generate output filename
                output_filename = file_storage.generate_output_filename(job["upload_filename"])
                output_path = file_storage.get_output_file_path(output_filename)
                
                self.update_job_status(job_id, "processing", output_filename=output_filename, progress=30)
                
                # Process video with FFmpeg
                await self._process_with_ffmpeg(input_path, output_path, job_id)
                
                # Verify output file was created
                if not file_storage.file_exists(output_path):
                    raise Exception("Output file was not created")
                
                # Update job completion
                self.update_job_status(
                    job_id, 
                    "completed", 
                    progress=100,
                    completed_at=datetime.now(),
                    output_size=file_storage.get_file_size(output_path)
                )
                
                return self.jobs[job_id]
                
            finally:
                # Always release the lock
                processing_lock.release()
                
        except HTTPException:
            raise
        except Exception as e:
            self.update_job_status(job_id, "failed", error=str(e), progress=0)
            if processing_lock.is_locked():
                processing_lock.release()
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    
    async def _process_with_ffmpeg(self, input_path: Path, output_path: Path, job_id: str):
        """Process video using FFmpeg with speed adjustment"""
        try:
            
            # First, get video duration to calculate trim point
            duration_cmd = [
                '/usr/bin/ffprobe',
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                str(input_path)
            ]
            
            # Get video duration
            duration_process = subprocess.run(
                duration_cmd,
                capture_output=True,
                text=True
            )
            
            if duration_process.returncode != 0:
                raise Exception("Failed to get video duration")
            
            total_duration = float(duration_process.stdout.strip())
            
            # Calculate new duration (remove 0.1% from end)
            trim_percentage = 0.2  # 0.1% = 0.001
            new_duration = total_duration * (1 - trim_percentage)
            
            
            
            # Step 1: Process the main video (speed up and trim)
            temp_processed = str(output_path).replace('.mp4', '_temp.mp4')

            cmd1 = [
                '/usr/bin/ffmpeg',
                '-i', str(input_path),
                '-t', str(new_duration),
                '-filter:v', f'setpts=PTS/{config.SPEED_MULTIPLIER}',
                '-filter:a', f'atempo={config.SPEED_MULTIPLIER}',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'fast',
                '-y',
                temp_processed
            ]

            # Step 2: Create black screen with text
            black_screen_file = str(output_path).replace('.mp4', '_black.mp4')

            cmd2 = [
                '/usr/bin/ffmpeg',
                '-f', 'lavfi', '-i', 'color=c=black:s=360x480:d=5',
                '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100:duration=1.5',
                '-filter_complex', '[0:v]drawtext=text="Follow For More":fontcolor=white:fontsize=24:x=(w-text_w)/2:y=(h-text_h)/2[v]',
                '-map', '[v]',
                '-map', '1:a',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-shortest',
                '-y',
                black_screen_file
            ]

            # Step 3: Concatenate both videos
            cmd3 = [
                '/usr/bin/ffmpeg',
                '-i', temp_processed,
                '-i', black_screen_file,
                '-filter_complex', '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]',
                '-map', '[outv]',
                '-map', '[outa]',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'fast',
                '-movflags', '+faststart',
                '-y',
                str(output_path)
            ]

            # Update progress
            self.update_job_status(job_id, "processing", progress=40)
            
            def run_ffmpeg_commands():
                try:
                    # Execute all three commands
                    process1 = subprocess.run(cmd1, capture_output=True, text=True)
                    if process1.returncode != 0:
                        return None, process1.stderr, process1.returncode
                    
                    process2 = subprocess.run(cmd2, capture_output=True, text=True)
                    if process2.returncode != 0:
                        return None, process2.stderr, process2.returncode
                    
                    process3 = subprocess.run(cmd3, capture_output=True, text=True)
                    if process3.returncode != 0:
                        return None, process3.stderr, process3.returncode
                    
                    # Clean up temp files
                    import os
                    if os.path.exists(temp_processed):
                        os.remove(temp_processed)
                    if os.path.exists(black_screen_file):
                        os.remove(black_screen_file)
                    
                    return process3.stdout, process3.stderr, 0
                    
                except Exception as e:
                    # Clean up temp files on error
                    import os
                    if os.path.exists(temp_processed):
                        os.remove(temp_processed)
                    if os.path.exists(black_screen_file):
                        os.remove(black_screen_file)
                    return None, str(e), 1
            
            # Run FFmpeg in thread executor with timeout
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                try:
                    stdout, stderr, returncode = await asyncio.wait_for(
                        loop.run_in_executor(executor, run_ffmpeg_commands),
                        timeout=config.FFMPEG_TIMEOUT
                    )
                    
                    if returncode != 0:
                        error_msg = stderr if stderr else "Unknown FFmpeg error"
                        raise Exception(f"FFmpeg failed: {error_msg}")
                    
                    # Update progress
                    self.update_job_status(job_id, "processing", progress=90)
                    
                except asyncio.TimeoutError:
                    raise Exception("Video processing timed out")
                    
        except Exception as e:
            raise Exception(f"FFmpeg processing error: {str(e)}")
                
    def cleanup_job(self, job_id: str) -> Dict[str, Any]:
        """Clean up job files and remove from memory"""
        cleanup_results = file_storage.cleanup_temp_files(job_id)
        
        # Remove job from memory
        if job_id in self.jobs:
            del self.jobs[job_id]
            cleanup_results["job_removed"] = True
        else:
            cleanup_results["job_removed"] = False
        
        return cleanup_results
    
    def get_all_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get all jobs (for debugging/monitoring)"""
        return self.jobs
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        total_jobs = len(self.jobs)
        status_counts = {}
        
        for job in self.jobs.values():
            status = job["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total_jobs": total_jobs,
            "status_counts": status_counts,
            "current_processing": processing_lock.get_current_job(),
            "lock_status": processing_lock.get_status()
        }

# Global processor instance
video_processor = VideoProcessor()
