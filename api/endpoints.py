from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Dict, Any
import asyncio
from utils.validation import VideoValidator
import os
from core.processor import video_processor
from core.storage import file_storage
from utils.cleanup import cleanup_manager
from middleware.processing_lock import processing_lock

router = APIRouter()

@router.post("/upload", response_model=Dict[str, Any])
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Upload a video file for processing
    Returns job ID and initial status
    """
    try:
        # Basic file validation
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Check if server is busy
        if processing_lock.is_locked():
            current_job = processing_lock.get_current_job()
            raise HTTPException(
                status_code=429, 
                detail=f"Server busy. Job {current_job} is currently being processed."
            )
        
        # Save uploaded file
        upload_filename, file_path = await file_storage.save_upload_file(file)
        
        
        # CRITICAL FIX: Validate the video BEFORE starting background task
        # This prevents the "response already started" error
        try:
            video_info = await VideoValidator.full_video_validation(file_path, file.filename)
        except HTTPException as validation_error:
            # Clean up the uploaded file if validation fails
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            raise validation_error
        
        # Create processing job
        job_id = video_processor.create_job(file.filename, upload_filename)
        
        # Start processing in background
        background_tasks.add_task(video_processor.process_video, job_id)
        
        return {
            "job_id": job_id,
            "status": "uploaded",
            "message": "File uploaded successfully. Processing started.",
            "original_filename": file.filename,
            "upload_filename": upload_filename,
            "video_info": video_info  # Optional: include validation results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/status/{job_id}", response_model=Dict[str, Any])
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get the status of a processing job
    Returns detailed job information
    """
    try:
        job_status = video_processor.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Add processing lock info if this job is currently processing
        response = job_status.copy()
        
        if processing_lock.get_current_job() == job_id:
            response["processing_duration"] = processing_lock.get_processing_duration()
            response["is_currently_processing"] = True
        else:
            response["is_currently_processing"] = False
        
        # Convert datetime objects to strings for JSON serialization
        for key in ["created_at", "started_at", "completed_at"]:
            if response.get(key):
                response[key] = response[key].isoformat()
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.get("/download/{job_id}")
async def download_processed_video(job_id: str):
    """
    Download the processed video file
    Returns the processed video file
    """
    try:
        job_status = video_processor.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job_status["status"] != "completed":
            raise HTTPException(
                status_code=400, 
                detail=f"Job not completed. Current status: {job_status['status']}"
            )
        
        output_filename = job_status.get("output_filename")
        if not output_filename:
            raise HTTPException(status_code=500, detail="Output filename not found")
        
        output_path = file_storage.get_output_file_path(output_filename)
        
        if not file_storage.file_exists(output_path):
            raise HTTPException(status_code=404, detail="Processed file not found")
        
        # Generate download filename
        original_filename = job_status["original_filename"]
        download_filename = f"speedup_{original_filename}"
        
        return FileResponse(
            path=str(output_path),
            filename=download_filename,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename={download_filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

# Additional utility endpoints (optional - for monitoring and debugging)

@router.get("/server/status")
async def get_server_status() -> Dict[str, Any]:
    """Get server status and statistics"""
    try:
        return {
            "server_status": "running",
            "processing_lock": processing_lock.get_status(),
            "processing_stats": video_processor.get_processing_stats(),
            "directory_stats": cleanup_manager.get_directory_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server status check failed: {str(e)}")

@router.post("/cleanup/old-files")
async def cleanup_old_files() -> Dict[str, Any]:
    """Clean up old temporary files"""
    try:
        results = cleanup_manager.cleanup_old_files()
        return {
            "message": "Cleanup completed",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@router.delete("/job/{job_id}")
async def delete_job(job_id: str) -> Dict[str, Any]:
    """Delete a job and its associated files"""
    try:
        job_status = video_processor.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Don't allow deletion of currently processing job
        if processing_lock.get_current_job() == job_id:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete job that is currently being processed"
            )
        
        # Clean up job files
        cleanup_results = video_processor.cleanup_job(job_id)
        
        return {
            "message": f"Job {job_id} deleted successfully",
            "cleanup_results": cleanup_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Job deletion failed: {str(e)}")

@router.get("/jobs")
async def list_all_jobs() -> Dict[str, Any]:
    """List all jobs (for debugging/monitoring)"""
    try:
        jobs = video_processor.get_all_jobs()
        
        # Convert datetime objects to strings for JSON serialization
        serialized_jobs = {}
        for job_id, job_data in jobs.items():
            job_copy = job_data.copy()
            for key in ["created_at", "started_at", "completed_at"]:
                if job_copy.get(key):
                    job_copy[key] = job_copy[key].isoformat()
            serialized_jobs[job_id] = job_copy
        
        return {
            "total_jobs": len(jobs),
            "jobs": serialized_jobs
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")