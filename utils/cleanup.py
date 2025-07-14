import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
from core.config import config
from core.storage import file_storage

class CleanupManager:
    """Manages cleanup of temporary files"""
    
    @staticmethod
    def get_old_files(directory: Path, max_age_seconds: int = None) -> List[Path]:
        """
        Get files older than specified age
        Default age from config.CLEANUP_AFTER_SECONDS
        """
        if max_age_seconds is None:
            max_age_seconds = config.CLEANUP_AFTER_SECONDS
        
        cutoff_time = datetime.now() - timedelta(seconds=max_age_seconds)
        old_files = []
        
        try:
            for file_path in directory.glob("*"):
                if file_path.is_file():
                    # Get file modification time
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        old_files.append(file_path)
        except Exception:
            pass
        
        return old_files
    
    @staticmethod
    def cleanup_old_files() -> Dict[str, any]:
        """
        Clean up old files from upload and output directories
        Returns cleanup statistics
        """
        results = {
            "upload_files_deleted": 0,
            "output_files_deleted": 0,
            "upload_files_failed": 0,
            "output_files_failed": 0,
            "total_size_freed": 0,
            "errors": []
        }
        
        # Clean upload directory
        old_upload_files = CleanupManager.get_old_files(config.UPLOAD_DIR)
        for file_path in old_upload_files:
            try:
                file_size = file_storage.get_file_size(file_path)
                if file_storage.delete_file(file_path):
                    results["upload_files_deleted"] += 1
                    results["total_size_freed"] += file_size
                else:
                    results["upload_files_failed"] += 1
            except Exception as e:
                results["upload_files_failed"] += 1
                results["errors"].append(f"Upload cleanup error: {str(e)}")
        
        # Clean output directory
        old_output_files = CleanupManager.get_old_files(config.OUTPUT_DIR)
        for file_path in old_output_files:
            try:
                file_size = file_storage.get_file_size(file_path)
                if file_storage.delete_file(file_path):
                    results["output_files_deleted"] += 1
                    results["total_size_freed"] += file_size
                else:
                    results["output_files_failed"] += 1
            except Exception as e:
                results["output_files_failed"] += 1
                results["errors"].append(f"Output cleanup error: {str(e)}")
        
        return results
    
    @staticmethod
    def force_cleanup_all() -> Dict[str, any]:
        """
        Force cleanup of all temporary files (regardless of age)
        Use with caution!
        """
        results = {
            "upload_files_deleted": 0,
            "output_files_deleted": 0,
            "errors": []
        }
        
        try:
            # Clean all upload files
            for file_path in config.UPLOAD_DIR.glob("*"):
                if file_path.is_file():
                    if file_storage.delete_file(file_path):
                        results["upload_files_deleted"] += 1
                    else:
                        results["errors"].append(f"Failed to delete: {file_path}")
            
            # Clean all output files
            for file_path in config.OUTPUT_DIR.glob("*"):
                if file_path.is_file():
                    if file_storage.delete_file(file_path):
                        results["output_files_deleted"] += 1
                    else:
                        results["errors"].append(f"Failed to delete: {file_path}")
                        
        except Exception as e:
            results["errors"].append(f"Force cleanup error: {str(e)}")
        
        return results
    
    @staticmethod
    def get_directory_stats() -> Dict[str, any]:
        """Get statistics about temp directories"""
        stats = {
            "upload_dir": {
                "file_count": 0,
                "total_size": 0,
                "files": []
            },
            "output_dir": {
                "file_count": 0,
                "total_size": 0,
                "files": []
            }
        }
        
        try:
            # Upload directory stats
            for file_path in config.UPLOAD_DIR.glob("*"):
                if file_path.is_file():
                    file_size = file_storage.get_file_size(file_path)
                    stats["upload_dir"]["file_count"] += 1
                    stats["upload_dir"]["total_size"] += file_size
                    stats["upload_dir"]["files"].append({
                        "name": file_path.name,
                        "size": file_size,
                        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    })
            
            # Output directory stats
            for file_path in config.OUTPUT_DIR.glob("*"):
                if file_path.is_file():
                    file_size = file_storage.get_file_size(file_path)
                    stats["output_dir"]["file_count"] += 1
                    stats["output_dir"]["total_size"] += file_size
                    stats["output_dir"]["files"].append({
                        "name": file_path.name,
                        "size": file_size,
                        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    })
                    
        except Exception as e:
            stats["error"] = str(e)
        
        return stats

# Global cleanup manager instance
cleanup_manager = CleanupManager() 
