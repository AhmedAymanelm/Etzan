import os
import uuid
import asyncio
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile, HTTPException

def init_cloudinary():
    if not cloudinary.config().cloud_name:
        cloudinary.config(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET')
        )

async def upload_audio_to_cloudinary(file: UploadFile, folder: str = "neuro_patterns_music") -> str:
    """
    Uploads an audio file to Cloudinary and returns the secure URL.
    """
    init_cloudinary()

    # Create a temporary file to save the uploaded chunks before sending to Cloudinary
    temp_file_path = f"/tmp/{uuid.uuid4()}_{file.filename}"
    
    try:
        # 1. Save locally (using standard open, file is small enough)
        content = await file.read()
        with open(temp_file_path, 'wb') as out_file:
            out_file.write(content)
                
        # 2. Upload to Cloudinary (resource_type="video" handles audio files too, or "auto")
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: cloudinary.uploader.upload(
                temp_file_path, 
                folder=folder, 
                resource_type="video" # Cloudinary uses 'video' or 'auto' for audio files
            )
        )
        
        return response['secure_url']
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloudinary upload error: {str(e)}")
    finally:
        # Cleanup temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

async def upload_image_to_cloudinary(file: UploadFile, folder: str = "team_members") -> str:
    """
    Uploads an image file to Cloudinary and returns the secure URL.
    """
    init_cloudinary()

    temp_file_path = f"/tmp/{uuid.uuid4()}_{file.filename}"
    
    try:
        content = await file.read()
        with open(temp_file_path, 'wb') as out_file:
            out_file.write(content)
                
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: cloudinary.uploader.upload(
                temp_file_path, 
                folder=folder, 
                resource_type="image"
            )
        )
        
        return response['secure_url']
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloudinary upload error: {str(e)}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
