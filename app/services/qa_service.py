from groq import Groq, APIError, APIConnectionError, APITimeoutError

from app.services.groq_service import GROQ_API_KEY, is_configured

QA_MODEL = "qwen/qwen3.6-27b"

MAX_HISTORY_MESSAGES = 10


def _build_system_prompt(document_text: str) -> str:
    return (
        "You are a careful assistant answering questions about a single document. "
        "Answer using only the information found in the document text below. "
        "Do not invent information and do not use outside knowledge. "
        "Pay special attention to names, dates, numbers, addresses, and designations, and reproduce them exactly as written in the document. "
        "Preserve Urdu terminology when relevant instead of translating it. "
        "The document text comes from OCR and may contain mistakes or unclear words. "
        "Treat it as potentially imperfect: if a detail looks like it could be an OCR error, answer using what is written and note the uncertainty rather than silently correcting or guessing a different value. "
        "If the answer is not present in the document, clearly state that it cannot be found in the document. "
        "The conversation may include earlier questions and answers about this same document. "
        "Use them only to understand what the current question refers to, such as a pronoun like 'his' or 'that date'. "
        "Always base your actual answer on the document text below, not on assumptions carried over from earlier answers, "
        "and never let the conversation history override or contradict the document. "
        "Answer clearly and concisely, in the same language as the current question where reasonable.\n\n"
        "DOCUMENT TEXT:\n"
        "\"\"\"\n"
        f"{document_text.strip()}\n"
        "\"\"\""
    )


def _sanitize_history(history) -> list:
    if not history:
        return []

    messages = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        content = entry.get("content")
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        messages.append({"role": role, "content": content.strip()})

    return messages[-MAX_HISTORY_MESSAGES:]


def ask_question(document_text: str, question: str, history=None) -> dict:
    if not is_configured():
        return {"status": "failed", "answer": None, "error": "GROQ_API_KEY is not configured."}

    if not document_text or not document_text.strip():
        return {"status": "failed", "answer": None, "error": "No document text available to answer from."}

    if not question or not question.strip():
        return {"status": "failed", "answer": None, "error": "Question cannot be empty."}

    messages = [{"role": "system", "content": _build_system_prompt(document_text)}]
    messages.extend(_sanitize_history(history))
    messages.append({"role": "user", "content": question.strip()})

    try:
        client = Groq(api_key=GROQ_API_KEY, timeout=60.0)
        completion = client.chat.completions.create(
            model=QA_MODEL,
            messages=messages,
            temperature=0.2,
            max_completion_tokens=1024,
            reasoning_format="hidden",
            reasoning_effort="none",
        )
    except APITimeoutError:
        return {"status": "failed", "answer": None, "error": "The request to Groq timed out. Please try again."}
    except APIConnectionError:
        return {"status": "failed", "answer": None, "error": "Could not connect to Groq. Check your network and try again."}
    except APIError as error:
        status_code = getattr(error, "status_code", None)
        if status_code == 401:
            return {"status": "failed", "answer": None, "error": "Groq rejected the API key. Check GROQ_API_KEY."}
        return {"status": "failed", "answer": None, "error": "Groq API returned an error. Please try again."}
    except Exception:
        return {"status": "failed", "answer": None, "error": "Unexpected error while contacting Groq."}

    if completion is None or not getattr(completion, "choices", None):
        return {"status": "failed", "answer": None, "error": "No response received from Groq."}

    try:
        answer = completion.choices[0].message.content
    except (IndexError, AttributeError):
        return {"status": "failed", "answer": None, "error": "Unexpected response format from Groq."}

    if not isinstance(answer, str) or not answer.strip():
        return {"status": "failed", "answer": None, "error": "Groq returned an empty answer."}

    return {"status": "success", "answer": answer.strip(), "error": None}