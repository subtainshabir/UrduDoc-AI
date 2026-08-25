import os
import json
import re
import threading
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
METADATA_FILE = os.path.join(DATA_DIR, "documents_metadata.json")

os.makedirs(DATA_DIR, exist_ok=True)

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_all() -> dict:
    if not os.path.isfile(METADATA_FILE):
        return {}
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return {}
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict) -> None:
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def create_metadata(document_id: str, original_filename: str, file_type: str, file_size: int) -> dict:
    with _lock:
        data = _load_all()
        if document_id in data:
            return data[document_id]

        record = {
            "document_id": document_id,
            "original_filename": original_filename,
            "file_type": file_type,
            "file_size": file_size,
            "upload_timestamp": _now(),
            "processing_status": "pending",
            "language": "unknown",
        }
        data[document_id] = record
        _save_all(data)
    return record


def get_metadata(document_id: str):
    data = _load_all()
    return data.get(document_id)


def update_metadata(document_id: str, **fields):
    with _lock:
        data = _load_all()
        record = data.get(document_id)
        if not record:
            return None
        record.update(fields)
        data[document_id] = record
        _save_all(data)
    return record


URDU_PATTERN = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
ENGLISH_PATTERN = re.compile(r"[A-Za-z]")


def detect_language(text: str) -> str:
    if not text or not text.strip():
        return "unknown"

    urdu_count = len(URDU_PATTERN.findall(text))
    english_count = len(ENGLISH_PATTERN.findall(text))

    if urdu_count == 0 and english_count == 0:
        return "unknown"
    if urdu_count > 0 and english_count == 0:
        return "urdu"
    if english_count > 0 and urdu_count == 0:
        return "english"

    urdu_ratio = urdu_count / (urdu_count + english_count)
    if urdu_ratio >= 0.85:
        return "urdu"
    if urdu_ratio <= 0.15:
        return "english"
    return "mixed"