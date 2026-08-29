import os
import io
import base64
from dotenv import load_dotenv
from groq import Groq, APIError, APIConnectionError, APITimeoutError
from PIL import Image, ImageOps

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

VISION_MODEL = "qwen/qwen3.6-27b"

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

MAX_IMAGE_DIMENSION = 2200
MIN_IMAGE_DIMENSION = 1100

OCR_PROMPT = (
    "You are an OCR engine reading a photo or scan of a handwritten or printed document. "
    "The document may be in Urdu (often handwritten in Nastaliq-style cursive script), English, or a mix of both, "
    "and may contain names, police or administrative designations, dates, numbers, and addresses.\n\n"
    "Carefully inspect the entire image from top to bottom before transcribing, including the margins and any faint or small writing. "
    "For handwritten Urdu, read the connected Nastaliq strokes character by character and word by word rather than guessing a word "
    "from its general shape, since many Urdu letters look similar in cursive handwriting.\n\n"
    "Follow these rules strictly:\n"
    "- Transcribe exactly what is visible. Do not translate any text.\n"
    "- Do not summarize, explain, describe, or rewrite the document in your own words.\n"
    "- Do not add information, words, or punctuation that are not visible in the image.\n"
    "- Do not silently guess an unclear word. If a word, name, or section is genuinely illegible, write [unclear] in its place.\n"
    "- Keep every word in its original language and script exactly as written.\n"
    "- Preserve names, ranks, and designations (for example police or administrative titles) exactly as spelled in the document, "
    "even if the spelling looks unusual.\n"
    "- Preserve numbers and dates exactly as they appear, character by character, including any local number formats or separators.\n"
    "- Preserve addresses exactly as written, including any abbreviations.\n"
    "- Preserve punctuation marks exactly as they appear; do not add or remove punctuation.\n"
    "- Preserve the original line breaks and paragraph structure so the transcription matches the layout of the document.\n"
    "- Do not add any headings, labels, or commentary that are not part of the original text.\n\n"
    "Return only the transcribed text, with nothing else before or after it."
)


def is_configured() -> bool:
    return bool(GROQ_API_KEY)


def _preprocess_image(image_path: str):
    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)

        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        width, height = img.size
        longer_side = max(width, height)

        if longer_side > MAX_IMAGE_DIMENSION:
            scale = MAX_IMAGE_DIMENSION / longer_side
            img = img.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS)
        elif longer_side < MIN_IMAGE_DIMENSION:
            scale = MIN_IMAGE_DIMENSION / longer_side
            img = img.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS)

        img = ImageOps.autocontrast(img, cutoff=1)

        if img.mode == "L":
            img = img.convert("RGB")

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=92)
        return buffer.getvalue()


def _encode_image_for_ocr(image_path: str):
    try:
        processed_bytes = _preprocess_image(image_path)
        return base64.b64encode(processed_bytes).decode("utf-8"), "image/jpeg"
    except Exception:
        with open(image_path, "rb") as image_file:
            raw_bytes = image_file.read()
        extension = os.path.splitext(image_path)[1].lower()
        mime_type = MIME_TYPES.get(extension, "image/jpeg")
        return base64.b64encode(raw_bytes).decode("utf-8"), mime_type


def extract_text_from_image(image_path: str) -> dict:
    if not is_configured():
        return {"status": "failed", "extracted_text": None, "error": "GROQ_API_KEY is not configured."}

    if not os.path.isfile(image_path):
        return {"status": "failed", "extracted_text": None, "error": "Image file not found."}

    extension = os.path.splitext(image_path)[1].lower()
    if extension not in MIME_TYPES:
        return {"status": "failed", "extracted_text": None, "error": "Unsupported image format."}

    try:
        base64_image, mime_type = _encode_image_for_ocr(image_path)
    except Exception:
        return {"status": "failed", "extracted_text": None, "error": "Could not read the image file."}

    try:
        client = Groq(api_key=GROQ_API_KEY, timeout=60.0)
        completion = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            temperature=0.2,
            max_completion_tokens=4096,
            reasoning_format="hidden",
            reasoning_effort="none",
        )
    except APITimeoutError:
        return {"status": "failed", "extracted_text": None, "error": "The request to Groq timed out. Please try again."}
    except APIConnectionError:
        return {"status": "failed", "extracted_text": None, "error": "Could not connect to Groq. Check your network and try again."}
    except APIError as error:
        status_code = getattr(error, "status_code", None)
        if status_code == 401:
            return {"status": "failed", "extracted_text": None, "error": "Groq rejected the API key. Check GROQ_API_KEY."}
        return {"status": "failed", "extracted_text": None, "error": "Groq API returned an error. Please try again."}
    except Exception:
        return {"status": "failed", "extracted_text": None, "error": "Unexpected error while contacting Groq."}

    if completion is None or not getattr(completion, "choices", None):
        return {"status": "failed", "extracted_text": None, "error": "No response received from Groq."}

    try:
        extracted_text = completion.choices[0].message.content
    except (IndexError, AttributeError):
        return {"status": "failed", "extracted_text": None, "error": "Unexpected response format from Groq."}

    if not isinstance(extracted_text, str):
        return {"status": "failed", "extracted_text": None, "error": "Unexpected response format from Groq."}

    if not extracted_text.strip():
        return {"status": "empty", "extracted_text": "", "error": "No text was detected in this image."}

    return {"status": "success", "extracted_text": extracted_text.strip(), "error": None}