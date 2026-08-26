from groq import Groq, APIError, APIConnectionError, APITimeoutError

from app.services.groq_service import GROQ_API_KEY, is_configured

QA_MODEL = "qwen/qwen3.6-27b"

QA_SYSTEM_PROMPT = (
    "You are a careful assistant answering questions about a single document. "
    "You will be given the full extracted text of that document and a question. "
    "Answer using only the information found in the document text. "
    "Do not invent information and do not use outside knowledge. "
    "Keep names, dates, numbers, and Urdu terminology exactly as they appear in the document. "
    "If the answer is not present in the document, clearly say that it cannot be found in the document. "
    "Answer clearly and concisely, in the same language as the question where reasonable."
)


def ask_question(document_text: str, question: str) -> dict:
    if not is_configured():
        return {"status": "failed", "answer": None, "error": "GROQ_API_KEY is not configured."}

    if not document_text or not document_text.strip():
        return {"status": "failed", "answer": None, "error": "No document text available to answer from."}

    if not question or not question.strip():
        return {"status": "failed", "answer": None, "error": "Question cannot be empty."}

    user_message = (
        "Document text:\n"
        "\"\"\"\n"
        f"{document_text}\n"
        "\"\"\"\n\n"
        f"Question: {question.strip()}"
    )

    try:
        client = Groq(api_key=GROQ_API_KEY, timeout=60.0)
        completion = client.chat.completions.create(
            model=QA_MODEL,
            messages=[
                {"role": "system", "content": QA_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_completion_tokens=1024,
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