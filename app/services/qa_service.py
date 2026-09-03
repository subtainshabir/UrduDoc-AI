import json
import re

from groq import Groq, APIError, APIConnectionError, APITimeoutError

from app.services.groq_service import GROQ_API_KEY, is_configured

QA_MODEL = "qwen/qwen3.6-27b"

MAX_HISTORY_MESSAGES = 10
MAX_DOCUMENT_CHARS = 12000
MAX_EVIDENCE_CHARS = 500

INSTRUCTIONS = (
    "- Use only the document text above to answer the question. Do not use outside knowledge.\n"
    "- Never invent or guess information that is not actually present in the document.\n"
    "- The document text comes from OCR and may contain mistakes; treat it as potentially imperfect.\n"
    "- Some words or phrases may be marked with [unclear], meaning the handwriting could not be confidently read.\n"
    "- Distinguish between two different situations: information that is missing from the document entirely "
    "(say it cannot be found in the document), and information that is present but marked [unclear] or otherwise "
    "hard to read (say that part of the document is unclear, rather than saying it cannot be found or guessing a value).\n"
    "- When the document contains an exact name, date, number, address, or designation relevant to the question, "
    "state it exactly as written rather than paraphrasing, rounding, or approximating it.\n"
    "- Preserve names, dates, numbers, addresses, designations, and Urdu terminology exactly as written; do not translate them.\n"
    "- This includes questions asking who a document was issued by or addressed to, how many people, places, or items "
    "are mentioned, or what happened according to the document; answer these the same way, using only what the document text says.\n"
    "- Answer directly: lead with the answer itself, in the same language as the question where reasonable. "
    "Avoid restating the question, unnecessary preamble, or explanations the question did not ask for.\n"
    "- Earlier questions and answers about this same document may be included as conversation turns below the DOCUMENT and QUESTION. "
    "Use them only to understand what the current question refers to (for example a pronoun like 'his' or 'that date'). "
    "Always base the actual answer on the document text, never on assumptions carried over from earlier answers, "
    "and never let the conversation history override or contradict the document.\n"
    "- Along with the answer, provide supporting evidence: a short excerpt copied word for word from the document text "
    "above that supports the answer. The evidence must be copied exactly as it appears in the document, not reworded, "
    "translated, or rewritten. Keep it short and directly relevant, not the whole document.\n"
    "- If the document does not support the answer (the information is missing or unclear), leave evidence as an empty string "
    "rather than inventing or guessing supporting text."
)

OUTPUT_FORMAT_INSTRUCTIONS = (
    "Respond with ONLY a single valid JSON object and nothing else before or after it, in exactly this form:\n"
    '{"answer": "<your answer to the question>", "evidence": "<a short excerpt copied exactly from the document text, or an empty string>"}'
)


def build_document_section(document_id: str, document_text: str, has_uncertain_text: bool = False) -> str:
    text = (document_text or "").strip()
    truncated = len(text) > MAX_DOCUMENT_CHARS
    if truncated:
        text = text[:MAX_DOCUMENT_CHARS]

    lines = [f"Document ID: {document_id}"]
    if has_uncertain_text:
        lines.append(
            "Note: this document's OCR text contains one or more [unclear] markers where the "
            "handwriting could not be confidently read."
        )
    lines.append('"""')
    lines.append(text)
    lines.append('"""')
    if truncated:
        lines.append(
            f"[Note: this document is long; only the first {MAX_DOCUMENT_CHARS} characters are shown above. "
            "If the answer might depend on text beyond this point, say the document is too long to fully confirm "
            "rather than guessing.]"
        )
    return "\n".join(lines)


def build_context(document_id: str, document_text: str, question: str, has_uncertain_text: bool = False) -> list:
    document_section = build_document_section(document_id, document_text, has_uncertain_text)

    system_content = (
        "You are a careful assistant answering questions about a single document.\n\n"
        "DOCUMENT:\n"
        f"{document_section}\n\n"
        "INSTRUCTIONS:\n"
        f"{INSTRUCTIONS}\n\n"
        f"{OUTPUT_FORMAT_INSTRUCTIONS}"
    )

    question_content = f"QUESTION:\n{question.strip()}"

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": question_content},
    ]


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


def _parse_answer_and_evidence(content: str):
    text = content.strip()

    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    parsed = None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            try:
                parsed = json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                parsed = None

    if isinstance(parsed, dict) and isinstance(parsed.get("answer"), str):
        answer = parsed.get("answer", "").strip()
        evidence = parsed.get("evidence", "")
        if not isinstance(evidence, str):
            evidence = ""
        return answer, evidence

    # The model did not return valid JSON. Fall back to treating the whole
    # reply as the answer so the user still gets a response, just without evidence.
    return text, ""


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _verify_evidence(evidence: str, document_text: str) -> str:
    if not evidence or not isinstance(evidence, str):
        return ""

    evidence = evidence.strip()
    if not evidence:
        return ""

    normalized_evidence = _normalize_for_match(evidence)
    normalized_document = _normalize_for_match(document_text)

    if not normalized_evidence or normalized_evidence not in normalized_document:
        return ""

    if len(evidence) > MAX_EVIDENCE_CHARS:
        evidence = evidence[:MAX_EVIDENCE_CHARS].rstrip()

    return evidence


def ask_question(document_id: str, document_text: str, question: str, history=None, has_uncertain_text: bool = False) -> dict:
    if not is_configured():
        return {"status": "failed", "answer": None, "evidence": None, "error": "GROQ_API_KEY is not configured."}

    if not document_text or not document_text.strip():
        return {"status": "failed", "answer": None, "evidence": None, "error": "No document text available to answer from."}

    if not question or not question.strip():
        return {"status": "failed", "answer": None, "evidence": None, "error": "Question cannot be empty."}

    system_message, question_message = build_context(document_id, document_text, question, has_uncertain_text)

    messages = [system_message]
    messages.extend(_sanitize_history(history))
    messages.append(question_message)

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
        return {"status": "failed", "answer": None, "evidence": None, "error": "The request to Groq timed out. Please try again."}
    except APIConnectionError:
        return {"status": "failed", "answer": None, "evidence": None, "error": "Could not connect to Groq. Check your network and try again."}
    except APIError as error:
        status_code = getattr(error, "status_code", None)
        if status_code == 401:
            return {"status": "failed", "answer": None, "evidence": None, "error": "Groq rejected the API key. Check GROQ_API_KEY."}
        return {"status": "failed", "answer": None, "evidence": None, "error": "Groq API returned an error. Please try again."}
    except Exception:
        return {"status": "failed", "answer": None, "evidence": None, "error": "Unexpected error while contacting Groq."}

    if completion is None or not getattr(completion, "choices", None):
        return {"status": "failed", "answer": None, "evidence": None, "error": "No response received from Groq."}

    try:
        raw_content = completion.choices[0].message.content
    except (IndexError, AttributeError):
        return {"status": "failed", "answer": None, "evidence": None, "error": "Unexpected response format from Groq."}

    if not isinstance(raw_content, str) or not raw_content.strip():
        return {"status": "failed", "answer": None, "evidence": None, "error": "Groq returned an empty answer."}

    answer, evidence_raw = _parse_answer_and_evidence(raw_content)

    if not answer:
        return {"status": "failed", "answer": None, "evidence": None, "error": "Groq returned an empty answer."}

    verified_evidence = _verify_evidence(evidence_raw, document_text)

    return {"status": "success", "answer": answer, "evidence": verified_evidence, "error": None}