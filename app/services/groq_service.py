import os
import base64
from dotenv import load_dotenv
from groq import Groq, APIError, APIConnectionError, APITimeoutError

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

VISION_MODEL = "qwen/qwen3.6-27b"

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

OCR_PROMPT = (
    "You are an OCR engine reading a photo or scan of a handwritten or printed document. "
    "The document may contain Urdu, English, numbers, dates, names, addresses, or a mix of these. "
    "Read all visible text exactly as written and transcribe it. "
    "Keep every word in its original language and script. Do not translate anything. "
    "Do not summarize, explain, or describe the document. "
    "Preserve the line breaks and layout of the original text as closely as possible. "
    "Preserve numbers, dates, names, addresses, and official terms exactly as written. "
    "If a word or section is unclear or illegible, write [unclear] in its place instead of guessing. "
    "Do not add any text, headings, or comments that are not visible in the image. "
    "Return only the transcribed text."
)


def is_configured() -> bool:
    return bool(GROQ_API_KEY)


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def extract_text_from_image(image_path: str) -> dict:
    if not is_configured():
        return {"status": "failed", "error": "GROQ_API_KEY is not configured."}

    if not os.path.isfile(image_path):
        return {"status": "failed", "error": "Image file not found."}

    extension = os.path.splitext(image_path)[1].lower()
    mime_type = MIME_TYPES.get(extension)
    if not mime_type:
        return {"status": "failed", "error": "Unsupported image format."}

    try:
        base64_image = _encode_image(image_path)
    except Exception:
        return {"status": "failed", "error": "Could not read the image file."}

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
            max_completion_tokens=2048,
        )
    except APITimeoutError:
        return {"status": "failed", "error": "The request to Groq timed out. Please try again."}
    except APIConnectionError:
        return {"status": "failed", "error": "Could not connect to Groq. Check your network and try again."}
    except APIError as error:
        status_code = getattr(error, "status_code", None)
        if status_code == 401:
            return {"status": "failed", "error": "Groq rejected the API key. Check GROQ_API_KEY."}
        return {"status": "failed", "error": "Groq API returned an error. Please try again."}
    except Exception:
        return {"status": "failed", "error": "Unexpected error while contacting Groq."}

    try:
        extracted_text = completion.choices[0].message.content
    except (IndexError, AttributeError):
        return {"status": "failed", "error": "Unexpected response format from Groq."}

    if not extracted_text or not extracted_text.strip():
        return {"status": "failed", "error": "Groq returned an empty response."}

    return {"status": "success", "extracted_text": extracted_text.strip()}