import asyncio
from datetime import datetime
from typing import Optional

class ProcessingLock:
    """Global lock to ensure only one video is processed at a time"""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._current_job_id: Optional[str] = None
        self._processing_start_time: Optional[datetime] = None
        self._is_processing = False
    
    async def acquire(self, job_id: str) -> bool:
        """
        Try to acquire the processing lock
        Returns True if acquired, False if already locked
        """
        if self._lock.locked():
            return False
        
        await self._lock.acquire()
        self._current_job_id = job_id
        self._processing_start_time = datetime.now()
        self._is_processing = True
        return True
    
    def release(self):
        """Release the processing lock"""
        if self._lock.locked():
            self._current_job_id = None
            self._processing_start_time = None
            self._is_processing = False
            self._lock.release()
    
    def is_locked(self) -> bool:
        """Check if processing lock is currently held"""
        return self._lock.locked()
    
    def get_current_job(self) -> Optional[str]:
        """Get the ID of currently processing job"""
        return self._current_job_id
    
    def get_processing_duration(self) -> Optional[float]:
        """Get how long current job has been processing (in seconds)"""
        if self._processing_start_time:
            return (datetime.now() - self._processing_start_time).total_seconds()
        return None
    
    def get_status(self) -> dict:
        """Get current lock status"""
        return {
            "is_processing": self._is_processing,
            "current_job_id": self._current_job_id,
            "processing_duration": self.get_processing_duration()
        }

# Global lock instance
processing_lock = ProcessingLock() 
