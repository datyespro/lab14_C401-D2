import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DOCUMENT_DIR = BASE_DIR / "documents"
OUTPUT_PATH = BASE_DIR / "golden_set.jsonl"
MODEL_NAME = "gemini-2.5-flash"

load_dotenv(BASE_DIR.parent / ".env")


def load_documents() -> Dict[str, str]:
    documents: Dict[str, str] = {}
    for file_path in sorted(DOCUMENT_DIR.glob("*.txt")):
        documents[file_path.stem] = file_path.read_text(encoding="utf-8").strip()
    return documents


def snippet(text: str, max_chars: int = 260) -> str:
    cleaned = " ".join(text.split())
    return cleaned[:max_chars]


def build_prompt(docs: Dict[str, str], num_pairs: int) -> str:
    hard_cases_guide = (BASE_DIR / "HARD_CASES_GUIDE.md").read_text(encoding="utf-8")
    doc_blocks = []
    for name, content in docs.items():
        doc_blocks.append(f"[{name}]\n{content}")

    return f"""You are generating a compact golden dataset for a RAG benchmark.

Use only the provided documents and the hard-case guidance. Write in Vietnamese.

Hard-case guidance:
{hard_cases_guide}

Documents:
{chr(10).join(doc_blocks)}

Return strictly valid JSON only, no markdown fences, no extra commentary.
Generate exactly {num_pairs} items as a JSON array.

Each item must have this schema:
{{
  "question": string,
  "expected_answer": string,
  "context": string,
  "expected_retrieval_ids": [string],
  "metadata": {{
    "difficulty": "easy" | "medium" | "hard",
    "type": string,
    "source_docs": string,
    "notes": string optional
  }}
}}

Rules:
- Cover the corpus with a mix of factual, policy-detail, FAQ, multi-document, adversarial prompt injection, conflict-check, and out-of-context cases.
- Keep the dataset small and useful; do not exceed {num_pairs} items.
- At least 2 items must be hard cases.
- expected_retrieval_ids should contain the most relevant document ids.
- context should be a short excerpt or synthesis grounded in the source documents.
- expected_answer must be concise and fully supported by the documents.
- Do not invent policies or facts not present in the documents.

Prefer questions that look realistic for a support or policy agent.
"""


def parse_generated_cases(raw_text: str) -> List[Dict[str, Any]]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1) if cleaned.startswith("json\n") else cleaned

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(cleaned[start : end + 1])

    if not isinstance(parsed, list):
        raise ValueError("Gemini output must be a JSON array.")
    return parsed


def normalize_case(item: Dict[str, Any], fallback_docs: List[str]) -> Dict[str, Any]:
    question = str(item.get("question", "")).strip()
    expected_answer = str(item.get("expected_answer", "")).strip()
    context = str(item.get("context", "")).strip()

    retrieval_ids = item.get("expected_retrieval_ids") or fallback_docs
    if not isinstance(retrieval_ids, list):
        retrieval_ids = fallback_docs
    retrieval_ids = [str(doc_id).strip() for doc_id in retrieval_ids if str(doc_id).strip()]

    metadata = item.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    normalized_metadata: Dict[str, str] = {
        "difficulty": str(metadata.get("difficulty", "medium")),
        "type": str(metadata.get("type", "fact-check")),
        "source_docs": str(metadata.get("source_docs", ",".join(fallback_docs))),
    }
    if metadata.get("notes"):
        normalized_metadata["notes"] = str(metadata["notes"])

    return {
        "question": question,
        "expected_answer": expected_answer,
        "context": context or snippet(" ".join(fallback_docs)),
        "expected_retrieval_ids": retrieval_ids,
        "metadata": normalized_metadata,
    }


async def generate_dataset(num_pairs: int = 8) -> List[Dict]:
    docs = load_documents()
    prompt = build_prompt(docs, num_pairs=num_pairs)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is missing. Add it to .env before running the generator.")

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is not installed. Run `pip install -r requirements.txt` after adding google-genai."
        ) from exc

    client = genai.Client(api_key=api_key)

    def _call_gemini() -> List[Dict[str, Any]]:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        text = getattr(response, "text", None) or ""
        if not text:
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                parts = candidates[0].content.parts if candidates[0].content else []
                text = "".join(getattr(part, "text", "") for part in parts)
        return parse_generated_cases(text)

    parsed_cases = await asyncio.to_thread(_call_gemini)

    fallback_docs = list(docs.keys())
    normalized_cases = [normalize_case(item, fallback_docs) for item in parsed_cases[:num_pairs]]
    return normalized_cases


async def generate_qa_from_text(text: str, num_pairs: Optional[int] = None) -> List[Dict]:
    """
    Generate a compact gold dataset from the documents in data/documents.

    The text argument is kept for backward compatibility with the original
    lab scaffold, but the generator now uses the real document corpus.
    """
    _ = text
    dataset = await generate_dataset()
    if num_pairs is None or num_pairs <= 0 or num_pairs >= len(dataset):
        return dataset
    return dataset[:num_pairs]


async def main():
    qa_pairs = await generate_qa_from_text("", num_pairs=None)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file_handle:
        for pair in qa_pairs:
            file_handle.write(json.dumps(pair, ensure_ascii=False) + "\n")

    print(f"Done! Saved {len(qa_pairs)} cases to {OUTPUT_PATH.as_posix()}")


if __name__ == "__main__":
    asyncio.run(main())
