from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header
from typing import Optional
from services.model_service import analyze_crop_image_local
from utils.security import decode_token
from utils.database import log_user_history
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/analyze")
async def analyze_disease(
    file: UploadFile = File(...),
    crop: Optional[str] = Form(None),
    authorization: str = Header(None)
):
    """
    Upload a crop/leaf image → get disease diagnosis + treatment plan using local TensorFlow model
    Optionally accepts a 'crop' form parameter to filter model predictions to a specific crop.
    """
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG/WEBP images allowed")

    try:
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail="Image file is empty")
        
        if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=413, detail="Image file too large (max 10MB)")

        result = await analyze_crop_image_local(image_bytes, crop_hint=crop)
        
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            payload = decode_token(token)
            if payload and "sub" in payload:
                log_user_history(payload["sub"], "Disease Analysis", {
                    "crop": crop or "Unknown",
                    "diagnosis": result.get("disease", "Unknown"),
                    "confidence": result.get("confidence", 0)
                })
                
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Disease analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in disease analysis: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while analyzing the image")
