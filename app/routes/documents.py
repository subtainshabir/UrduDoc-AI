from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import uuid

from app.services import groq_service
from app.services import text_cleaning_service
from app.services import storage_service

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _is_valid_document_id(document_id: str) -> bool:
    return bool(document_id) and "/" not in document_id and "\\" not in document_id and ".." not in document_id


def _public_view(record):
    if not record:
        return None
    view = dict(record)
    view.pop("file_path", None)
    return view


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

    record = storage_service.create_document(
        document_id=saved_filename,
        original_filename=file.filename,
        file_type=file.content_type,
        file_size=len(contents),
        file_path=saved_path,
    )

    return {
        "status": "success",
        "document_id": saved_filename,
        "original_filename": file.filename,
        "saved_filename": saved_filename,
        "content_type": file.content_type,
        "size_bytes": len(contents),
        "metadata": _public_view(record),
    }


@router.get("/api/documents")
async def list_documents():
    records = storage_service.list_documents()
    records.sort(key=lambda r: r.get("upload_timestamp", ""), reverse=True)
    return [
        {
            "document_id": r.get("document_id"),
            "filename": r.get("original_filename"),
            "language": r.get("language"),
            "processing_status": r.get("processing_status"),
            "upload_timestamp": r.get("upload_timestamp"),
        }
        for r in records
    ]


@router.post("/api/documents/{document_id}/ocr")
async def ocr_document(document_id: str):
    if not _is_valid_document_id(document_id):
        raise HTTPException(status_code=400, detail="Invalid document id.")

    record = storage_service.get_document(document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found.")

    image_path = record.get("file_path")
    if not image_path or not os.path.isfile(image_path):
        storage_service.update_document(document_id, processing_status="failed")
        raise HTTPException(status_code=404, detail="Image file is missing.")

    storage_service.update_document(document_id, processing_status="processing")

    result = groq_service.extract_text_from_image(image_path)
    status = result.get("status", "failed")
    extracted_text = result.get("extracted_text")
    error = result.get("error")

    if status == "success":
        extracted_text = text_cleaning_service.clean_text(extracted_text)

        text_path = f"{image_path}.txt"
        try:
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(extracted_text)
        except Exception:
            pass

        language = storage_service.detect_language(extracted_text)
        record = storage_service.update_document(
            document_id,
            processing_status="completed",
            language=language,
            extracted_text=extracted_text,
        )
    elif status == "empty":
        record = storage_service.update_document(
            document_id,
            processing_status="completed",
            language="unknown",
            extracted_text="",
        )
    else:
        record = storage_service.update_document(document_id, processing_status="failed")

    return {
        "document_id": document_id,
        "status": status,
        "extracted_text": extracted_text,
        "error": error,
        "metadata": _public_view(record),
    }


@router.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    if not _is_valid_document_id(document_id):
        raise HTTPException(status_code=400, detail="Invalid document id.")

    record = storage_service.get_document(document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found.")

    image_path = record.get("file_path")
    if image_path and os.path.isfile(image_path):
        try:
            os.remove(image_path)
        except OSError:
            pass

    if image_path:
        text_path = f"{image_path}.txt"
        if os.path.isfile(text_path):
            try:
                os.remove(text_path)
            except OSError:
                pass

    storage_service.delete_document(document_id)

    return {"document_id": document_id, "status": "deleted"}