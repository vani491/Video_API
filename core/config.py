import os
import tempfile
from pathlib import Path
from typing import Optional

class Config:
    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    
    # Get the project root directory (where main.py is located)
    PROJECT_ROOT = Path(__file__).parent.parent
    
    # File upload settings
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes
    ALLOWED_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv'}
    
    # Video processing settings - FIXED: 0.1% speed increase
    SPEED_MULTIPLIER = 1.001  # Speed up by 0.1% (1 + 0.001)
    MAX_VIDEO_DURATION = 65  # seconds (as per requirements)
    MIN_VIDEO_DURATION = 1   # seconds
    
    # Storage settings - Production-ready paths
    if ENVIRONMENT == "production":
        # Use system temp directory for AWS
        TEMP_DIR = Path(tempfile.gettempdir()) / "video_processor"
    else:
        # Use local temp for development
        TEMP_DIR = PROJECT_ROOT / "temp"
    
    UPLOAD_DIR = TEMP_DIR / "uploads"
    OUTPUT_DIR = TEMP_DIR / "outputs"
    
    # FFmpeg settings
    FFMPEG_VIDEO_CODEC = "libx264"
    FFMPEG_AUDIO_CODEC = "aac"
    FFMPEG_TIMEOUT = 300  # 5 minutes
    
    # API settings
    MAX_CONCURRENT_UPLOADS = 1  # Only one upload at a time
    
    # Security settings
    CORS_ORIGINS = [
        "http://localhost:3000",  # Development
        "http://localhost:8000",  # Development
        "https://omnixone.com",
        "https://api.omnixone.com"
    
    ]
    
    # Logging settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Cleanup settings
    CLEANUP_INTERVAL = 3600  # 1 hour
    FILE_RETENTION_TIME = 3600  # 1 hour
    
    # Server settings
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8001"))  # Changed to 8001 for production
    
    def __init__(self):
        """Ensure directories exist"""
        self.setup_directories()
    
    @classmethod
    def setup_directories(cls):
        """Create necessary directories if they don't exist"""
        try:
            cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
            cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            # Set proper permissions for production
            if cls.ENVIRONMENT == "production":
                os.chmod(cls.TEMP_DIR, 0o755)
                os.chmod(cls.UPLOAD_DIR, 0o755)
                os.chmod(cls.OUTPUT_DIR, 0o755)
                
        except Exception as e:
            print(f" Failed to create directories: {str(e)}")
            raise
    
    @classmethod
    def get_upload_path(cls, filename: str) -> Path:
        """Get full path for uploaded file"""
        return cls.UPLOAD_DIR / filename
    
    @classmethod
    def get_output_path(cls, filename: str) -> Path:
        """Get full path for output file"""
        return cls.OUTPUT_DIR / filename
    
    @classmethod
    def cleanup_old_files(cls):
        """Remove old files based on retention time"""
        import time
        current_time = time.time()
        
        for directory in [cls.UPLOAD_DIR, cls.OUTPUT_DIR]:
            if directory.exists():
                for file_path in directory.iterdir():
                    if file_path.is_file():
                        file_age = current_time - file_path.stat().st_mtime
                        if file_age > cls.FILE_RETENTION_TIME:
                            try:
                                file_path.unlink()
                                print(f"  Cleaned up old file: {file_path.name}")
                            except Exception as e:
                                print(f" Failed to cleanup {file_path.name}: {str(e)}")

# Global config instance
config = Config()