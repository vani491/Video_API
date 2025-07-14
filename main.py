from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from api.endpoints import router
from core.config import config
import uvicorn

# Create FastAPI app
app = FastAPI(
    title="Video Speed-Up API",
    description="API for speeding up videos by 0.1% using FFmpeg",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")

# Setup directories on startup
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        # Create necessary directories
        config.setup_directories()
        print("✅ Application started successfully")
        print(f"📁 Upload directory: {config.UPLOAD_DIR}")
        print(f"📁 Output directory: {config.OUTPUT_DIR}")
        print(f"⚙️  Speed multiplier: {config.SPEED_MULTIPLIER}")
        print(f"📏 Max file size: {config.MAX_FILE_SIZE / (1024*1024):.1f}MB")
        print(f"⏱️  Max video duration: {config.MAX_VIDEO_DURATION}s")
    except Exception as e:
        print(f"❌ Startup failed: {str(e)}")
        raise

# Health check endpoint
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Video Speed-Up API is running",
        "version": "1.0.0",
        "endpoints": {
            "upload": "/api/v1/upload",
            "status": "/api/v1/status/{job_id}",
            "download": "/api/v1/download/{job_id}",
            "server_status": "/api/v1/server/status"
        }
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    return HTTPException(
        status_code=500,
        detail=f"Internal server error: {str(exc)}"
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )