"""
engine/retrieval_eval.py
Evaluates retrieval quality (Hit Rate, MRR, Chunk Errors).

VectorDB Strategy:
- Production: Plug in your real VectorDB client (Chroma, Qdrant, Weaviate…)
- Lab / Offline: Uses LightweightKeywordDB — TF-IDF-style scoring over the
  document corpus loaded from data/documents/*.txt — producing meaningful
  retrieved_ids that actually relate to the query.
"""

import asyncio
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


# ──────────────────────────────────────────────────────────
# Lightweight keyword / TF-IDF Mock Vector DB
# ──────────────────────────────────────────────────────────

class LightweightKeywordDB:
    """
    Mock Vector DB dựa trên TF-IDF đơn giản.
    Đọc các file .txt từ data/documents/ và index từ khoá.
    Kết quả query trả về document ids liên quan nhất, sắp xếp theo score.
    Không cần API, không cần embedding model.
    """

    def __init__(self, document_dir: str = "data/documents"):
        self.doc_dir = Path(document_dir)
        self._corpus: Dict[str, str] = {}       # doc_id → full text
        self._tf: Dict[str, Dict[str, float]] = {}  # doc_id → {term: tf}
        self._idf: Dict[str, float] = {}         # term → idf
        self._loaded = False

    def _tokenize(self, text: str) -> List[str]:
        """Tách từ đơn giản — loại bỏ ký tự đặc biệt, lowercase."""
        tokens = re.findall(r"\w+", text.lower(), re.UNICODE)
        return [t for t in tokens if len(t) > 1]

    def _load(self):
        """Load và index toàn bộ documents."""
        if self._loaded:
            return

        if self.doc_dir.exists():
            for path in sorted(self.doc_dir.glob("*.txt")):
                text = path.read_text(encoding="utf-8", errors="ignore").strip()
                if text:
                    self._corpus[path.stem] = text

        # Nếu không có documents thật → tạo corpus giả
        if not self._corpus:
            self._corpus = {
                "policy_handbook": (
                    "Chính sách hoàn tiền áp dụng trong 30 ngày kể từ ngày mua. "
                    "Sản phẩm phải còn nguyên vẹn và kèm hóa đơn. "
                    "Bảo hành 12 tháng bao gồm lỗi sản xuất. "
                    "Liên hệ hotline 1800 để được hỗ trợ đổi trả."
                ),
                "user_guide": (
                    "Hướng dẫn sử dụng tài khoản: đăng nhập, đổi mật khẩu, cài đặt bảo mật. "
                    "Vào Cài đặt > Bảo mật > Đổi mật khẩu để thay mật khẩu. "
                    "Thời gian hỗ trợ 8h-22h thứ Hai đến thứ Bảy."
                ),
                "faq": (
                    "Các câu hỏi thường gặp về sản phẩm và dịch vụ. "
                    "Email xác nhận được gửi trong vòng 5 phút sau khi đăng ký. "
                    "Kiểm tra spam nếu không nhận được email. "
                    "Giảm 10% khi mua từ 2 sản phẩm trở lên."
                ),
            }

        # ── Tính TF ──
        df: Dict[str, int] = {}
        for doc_id, text in self._corpus.items():
            tokens = self._tokenize(text)
            freq: Dict[str, int] = {}
            for t in tokens:
                freq[t] = freq.get(t, 0) + 1
            total = max(len(tokens), 1)
            self._tf[doc_id] = {t: cnt / total for t, cnt in freq.items()}
            for t in freq:
                df[t] = df.get(t, 0) + 1

        # ── Tính IDF ──
        n = len(self._corpus)
        self._idf = {
            t: math.log((n + 1) / (cnt + 1)) + 1
            for t, cnt in df.items()
        }

        self._loaded = True

    def query(self, text: str, top_k: int = 3) -> List[str]:
        """Trả về list doc_ids sắp xếp theo relevance score (TF-IDF)."""
        self._load()
        query_tokens = self._tokenize(text)
        if not query_tokens:
            return list(self._corpus.keys())[:top_k]

        scores: Dict[str, float] = {}
        for doc_id, tf_map in self._tf.items():
            score = 0.0
            for t in query_tokens:
                if t in tf_map:
                    score += tf_map[t] * self._idf.get(t, 1.0)
            scores[doc_id] = score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _ in ranked[:top_k]]

    async def query_async(self, text: str, top_k: int = 3) -> List[str]:
        """Async wrapper (chạy trong thread để không block event loop)."""
        return await asyncio.to_thread(self.query, text, top_k)


# ──────────────────────────────────────────────────────────
# Shim cho backward-compatibility với VectorDBConnection cũ
# ──────────────────────────────────────────────────────────

class VectorDBConnection:
    """
    Backward-compatible wrapper.
    Delegates thực sự về LightweightKeywordDB.
    """

    def __init__(self, uri: str = "http://localhost:8000", document_dir: str = "data/documents"):
        self.uri = uri
        self._db = LightweightKeywordDB(document_dir=document_dir)
        self.connected = False

    def connect(self):
        self._db._load()  # Pre-load index
        self.connected = True
        n_docs = len(self._db._corpus)
        print(f"[*] VectorDB (Keyword/TF-IDF) sẵn sàng — {n_docs} documents đã index")

    async def query(self, text: str, top_k: int = 3) -> List[str]:
        if not self.connected:
            raise ConnectionError("VectorDB is not connected. Call connect() first.")
        return await self._db.query_async(text, top_k)


# ──────────────────────────────────────────────────────────
# Retrieval Evaluator
# ──────────────────────────────────────────────────────────

class RetrievalEvaluator:
    """
    Tính toán các metrics đánh giá chất lượng Retrieval.
    Kết hợp VectorDB (TF-IDF hoặc thật) với các công thức Hit Rate / MRR.
    """

    def __init__(self, vector_db_uri: str = "http://localhost:8000",
                 document_dir: str = "data/documents"):
        self.vector_db = VectorDBConnection(uri=vector_db_uri, document_dir=document_dir)
        self.vector_db.connect()

    # ── Metrics ──────────────────────────────────────────

    def calculate_hit_rate(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        """Hit@K: 1 nếu ít nhất 1 expected_id nằm trong top-K retrieved."""
        if not expected_ids or not retrieved_ids:
            return 0.0
        top_retrieved = retrieved_ids[:top_k]
        return 1.0 if any(did in top_retrieved for did in expected_ids) else 0.0

    def calculate_mrr(self, expected_ids: List[str], retrieved_ids: List[str]) -> float:
        """Mean Reciprocal Rank: 1/position của expected_id đầu tiên tìm thấy."""
        if not expected_ids or not retrieved_ids:
            return 0.0
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in expected_ids:
                return 1.0 / (i + 1)
        return 0.0

    def analyze_chunk_errors(self, expected_ids: List[str], retrieved_ids: List[str]) -> Dict:
        """Chunk-level error analysis."""
        expected_set = set(expected_ids)
        retrieved_set = set(retrieved_ids)
        missing = list(expected_set - retrieved_set)
        noise = list(retrieved_set - expected_set)
        return {
            "missing_chunks": missing,
            "noise_chunks": noise,
            "is_perfect_match": len(missing) == 0 and len(noise) == 0,
            "precision": len(expected_set & retrieved_set) / max(len(retrieved_set), 1),
            "recall": len(expected_set & retrieved_set) / max(len(expected_set), 1),
        }

    # ── Scoring wrapper (dùng bởi BenchmarkRunner) ───────

    async def score(self, case: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrapper gọi bởi BenchmarkRunner.score(case, resp).
        Trả về dict tương thích với runner/regression_gate.

        Ngoài retrieval, cũng ước tính faithfulness/relevancy đơn giản
        bằng keyword overlap (proxy khi không có RAGAS).
        """
        expected_ids: List[str] = case.get("expected_retrieval_ids", [])
        question: str = case.get("question", "")
        expected_answer: str = case.get("expected_answer", "")
        agent_answer: str = response.get("answer", "")

        # Lấy retrieved_ids từ response nếu có,否则 query VectorDB
        retrieved_ids: List[str] = response.get("retrieved_ids", [])
        if not retrieved_ids:
            retrieved_ids = await self.vector_db.query(question, top_k=3)

        hit_rate = self.calculate_hit_rate(expected_ids, retrieved_ids)
        mrr = self.calculate_mrr(expected_ids, retrieved_ids)
        chunk_errors = self.analyze_chunk_errors(expected_ids, retrieved_ids)

        # ── Keyword-overlap proxy cho faithfulness & relevancy ──
        faithfulness = self._keyword_overlap(agent_answer, expected_answer)
        relevancy = self._keyword_overlap(agent_answer, question)

        return {
            "faithfulness": round(faithfulness, 4),
            "relevancy": round(relevancy, 4),
            "retrieval": {
                "hit_rate": hit_rate,
                "mrr": mrr,
                "retrieved_ids": retrieved_ids,
                "expected_ids": expected_ids,
                "errors": chunk_errors,
            },
        }

    def _keyword_overlap(self, text_a: str, text_b: str) -> float:
        """Jaccard similarity giữa tập từ khoá của 2 đoạn text."""
        if not text_a or not text_b:
            return 0.0
        tokens_a = set(re.findall(r"\w+", text_a.lower()))
        tokens_b = set(re.findall(r"\w+", text_b.lower()))
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)

    # ── Batch evaluation (standalone) ────────────────────

    async def evaluate_batch(self, dataset: List[Dict]) -> Dict:
        """
        Chạy eval retrieval cho toàn bộ dataset.
        Dataset phải có trường 'expected_retrieval_ids'.
        """
        if not dataset:
            return {"avg_hit_rate": 0.0, "avg_mrr": 0.0, "total_evaluated": 0, "detailed_analysis": []}

        total_hit_rate = 0.0
        total_mrr = 0.0
        error_analysis = []

        for case in dataset:
            expected = case.get("expected_retrieval_ids", [])
            retrieved = case.get("retrieved_ids")
            if not retrieved:
                question = case.get("question", "")
                retrieved = await self.vector_db.query(question, top_k=3)

            hit_rate = self.calculate_hit_rate(expected, retrieved)
            mrr = self.calculate_mrr(expected, retrieved)
            total_hit_rate += hit_rate
            total_mrr += mrr

            error_analysis.append({
                "question": case.get("question"),
                "expected_ids": expected,
                "retrieved_ids": retrieved,
                "hit_rate": hit_rate,
                "mrr": mrr,
                "errors": self.analyze_chunk_errors(expected, retrieved),
            })

        n = len(dataset)
        return {
            "avg_hit_rate": round(total_hit_rate / n, 4),
            "avg_mrr": round(total_mrr / n, 4),
            "total_evaluated": n,
            "detailed_analysis": error_analysis,
        }


# ──────────────────────────────────────────────────────────
# Quick standalone test
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json
    sys.stdout.reconfigure(encoding="utf-8")

    async def _test():
        ev = RetrievalEvaluator()

        # Ưu tiên dùng golden_set.jsonl thật nếu có
        golden_path = Path("data/golden_set.jsonl")
        if golden_path.exists():
            all_cases = [
                json.loads(l) for l in golden_path.read_text(encoding="utf-8").splitlines() if l.strip()
            ]
            sample = all_cases[:5]
            print(f"[Test] Dùng golden_set.jsonl — {len(all_cases)} cases tổng, test 5 đầu")
        else:
            # Fallback với IDs khớp documents thật
            sample = [
                {"question": "Chính sách hoàn tiền như thế nào?", "expected_retrieval_ids": ["policy_refund_v4"]},
                {"question": "Quy trình xử lý sự cố IT cấp P1 là gì?", "expected_retrieval_ids": ["sla_p1_2026"]},
                {"question": "Nhân viên được nghỉ phép bao nhiêu ngày?", "expected_retrieval_ids": ["hr_leave_policy"]},
            ]
            print("[Test] Dùng demo cases (golden_set.jsonl chưa có)")

        result = await ev.evaluate_batch(sample)
        print(f"\nHit Rate: {result['avg_hit_rate']:.4f}")
        print(f"MRR:      {result['avg_mrr']:.4f}")
        print(f"Cases:    {result['total_evaluated']}")
        for d in result["detailed_analysis"]:
            print(f"  Q: {d['question'][:55]}")
            print(f"     expected={d['expected_ids']}")
            print(f"     retrieved={d['retrieved_ids']}  hit={d['hit_rate']} mrr={d['mrr']:.2f}")

    asyncio.run(_test())
