import uuid
import aiofiles
from pathlib import Path
from typing import Optional, BinaryIO
from fastapi import UploadFile, HTTPException
from core.config import config

class FileStorage:
    """Handles file storage operations"""
    
    def __init__(self):
        # Ensure directories exist
        config.setup_directories()
    
    @staticmethod
    def generate_unique_filename(original_filename: str) -> str:
        """Generate unique filename with timestamp and UUID"""
        file_path = Path(original_filename)
        unique_id = str(uuid.uuid4())[:8]
        return f"{unique_id}_{file_path.name}"
    
    @staticmethod
    def generate_output_filename(input_filename: str) -> str:
        """Generate output filename for processed video"""
        file_path = Path(input_filename)
        stem = file_path.stem
        suffix = file_path.suffix
        return f"{stem}_speedup{suffix}"
    
    async def save_upload_file(self, upload_file: UploadFile) -> tuple[str, Path]:
        """
        Save uploaded file to temp directory
        Returns: (unique_filename, file_path)
        """
        try:
            # Generate unique filename
            unique_filename = self.generate_unique_filename(upload_file.filename)
            file_path = config.get_upload_path(unique_filename)
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                content = await upload_file.read()
                await f.write(content)
            
            return unique_filename, file_path
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file: {str(e)}"
            )
    
    @staticmethod
    def get_upload_file_path(filename: str) -> Path:
        """Get path to uploaded file"""
        return config.get_upload_path(filename)
    
    @staticmethod
    def get_output_file_path(filename: str) -> Path:
        """Get path to output file"""
        return config.get_output_path(filename)
    
    @staticmethod
    def file_exists(file_path: Path) -> bool:
        """Check if file exists"""
        return file_path.exists() and file_path.is_file()
    
    @staticmethod
    def get_file_size(file_path: Path) -> int:
        """Get file size in bytes"""
        if FileStorage.file_exists(file_path):
            return file_path.stat().st_size
        return 0
    
    @staticmethod
    def delete_file(file_path: Path) -> bool:
        """Delete a file safely"""
        try:
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False
    
    @staticmethod
    def cleanup_temp_files(job_id: str) -> dict:
        """
        Clean up temporary files for a specific job
        Returns cleanup results
        """
        results = {
            "upload_deleted": False,
            "output_deleted": False,
            "errors": []
        }
        
        try:
            # Find and delete upload file (contains job_id in filename)
            for file_path in config.UPLOAD_DIR.glob(f"{job_id}*"):
                if FileStorage.delete_file(file_path):
                    results["upload_deleted"] = True
                else:
                    results["errors"].append(f"Failed to delete upload: {file_path}")
            
            # Find and delete output file
            for file_path in config.OUTPUT_DIR.glob(f"*{job_id}*"):
                if FileStorage.delete_file(file_path):
                    results["output_deleted"] = True
                else:
                    results["errors"].append(f"Failed to delete output: {file_path}")
                    
        except Exception as e:
            results["errors"].append(f"Cleanup error: {str(e)}")
        
        return results

# Global storage instance
file_storage = FileStorage() 
