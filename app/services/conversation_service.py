import os
import json
import uuid
import threading
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONVERSATIONS_FILE = os.path.join(DATA_DIR, "conversations.json")

os.makedirs(DATA_DIR, exist_ok=True)

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_all() -> dict:
    if not os.path.isfile(CONVERSATIONS_FILE):
        return {}
    try:
        with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return {}
        data = json.loads(content)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _new_record(document_id: str) -> dict:
    return {
        "conversation_id": uuid.uuid4().hex,
        "document_id": document_id,
        "created_at": _now(),
        "updated_at": _now(),
        "messages": [],
    }


def _is_valid_record(record) -> bool:
    return (
        isinstance(record, dict)
        and isinstance(record.get("conversation_id"), str)
        and isinstance(record.get("document_id"), str)
        and isinstance(record.get("messages"), list)
    )


def get_conversation(document_id: str):
    data = _load_all()
    record = data.get(document_id)
    if not _is_valid_record(record):
        return None
    return record


def get_or_create_conversation(document_id: str) -> dict:
    with _lock:
        data = _load_all()
        record = data.get(document_id)
        if _is_valid_record(record):
            return record

        record = _new_record(document_id)
        data[document_id] = record
        _save_all(data)
    return record


def append_messages(document_id: str, messages: list) -> dict:
    with _lock:
        data = _load_all()
        record = data.get(document_id)
        if not _is_valid_record(record):
            record = _new_record(document_id)

        for message in messages or []:
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            content = message.get("content")
            timestamp = message.get("timestamp") or _now()
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                record["messages"].append({
                    "role": role,
                    "content": content.strip(),
                    "timestamp": timestamp,
                })

        record["updated_at"] = _now()
        data[document_id] = record
        _save_all(data)
    return record


def delete_conversation(document_id: str):
    with _lock:
        data = _load_all()
        record = data.pop(document_id, None)
        if record is not None:
            _save_all(data)
    return record