from PIL import Image
from fastapi import UploadFile, HTTPException
import io

MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/jpg']

async def pil_from_upload(upload_file: UploadFile) -> Image.Image:
    """Convert UploadFile to PIL Image with validation.
    
    Args:
        upload_file: FastAPI UploadFile object
        
    Returns:
        PIL Image object
        
    Raises:
        HTTPException: If validation fails
    """
    # Check mime type
    if upload_file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image type. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    
    # Read file content
    content = await upload_file.read()
    
    # Check size
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large. Maximum size: {MAX_IMAGE_SIZE / (1024*1024)}MB"
        )
    
    # Try to open as PIL Image
    try:
        image = Image.open(io.BytesIO(content))
        image.load()  # Verify it's a valid image
        return image
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image file: {str(e)}"
        )