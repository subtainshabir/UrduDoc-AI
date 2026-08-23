from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import uuid

from app.services import groq_service

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only JPG, PNG, and WEBP images are allowed.",
        )

    extension = ALLOWED_CONTENT_TYPES[file.content_type]
    saved_filename = f"{uuid.uuid4().hex}{extension}"
    saved_path = os.path.join(UPLOAD_DIR, saved_filename)

    try:
        contents = await file.read()
        with open(saved_path, "wb") as f:
            f.write(contents)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save the uploaded file.")

    return {
        "status": "success",
        "document_id": saved_filename,
        "original_filename": file.filename,
        "saved_filename": saved_filename,
        "content_type": file.content_type,
        "size_bytes": len(contents),
    }


@router.post("/api/documents/{document_id}/ocr")
async def ocr_document(document_id: str):
    if "/" in document_id or "\\" in document_id or ".." in document_id:
        raise HTTPException(status_code=400, detail="Invalid document id.")

    image_path = os.path.join(UPLOAD_DIR, document_id)

    if not os.path.isfile(image_path):
        raise HTTPException(status_code=404, detail="Document not found.")

    result = groq_service.extract_text_from_image(image_path)

    if result["status"] != "success":
        return {
            "document_id": document_id,
            "extracted_text": None,
            "status": "failed",
            "error": result.get("error", "OCR failed."),
        }

    text_path = f"{image_path}.txt"
    try:
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(result["extracted_text"])
    except Exception:
        pass

    return {
        "document_id": document_id,
        "extracted_text": result["extracted_text"],
        "status": "success",
    }