import asyncio
from typing import List, Dict, Optional

class VectorDBConnection:
    """
    Kết nối với Vector DB (Mô phỏng cho lab).
    Trong thực tế, bạn sẽ dùng các thư viện client như chromadb, qdrant_client, v.v.
    """
    def __init__(self, uri: str = "http://localhost:8000"):
        self.uri = uri
        self.connected = False
        
    def connect(self):
        # Giả lập quá trình kết nối với DB
        self.connected = True
        print(f"[*] Connected to Vector DB at {self.uri}")

    async def query(self, text: str, top_k: int = 3) -> List[str]:
        # Giả lập truy vấn Vector DB
        if not self.connected:
            raise ConnectionError("Vector DB is not connected.")
        # Trong thực tế, ở đây sẽ convert text thành embedding và query DB.
        await asyncio.sleep(0.05) # Mô phỏng network latency
        # Dummy trả về để tránh lỗi, thực tế sẽ là các document ID thật
        return ["dummy_doc_1", "dummy_doc_2"]


class RetrievalEvaluator:
    def __init__(self, vector_db_uri: str = "http://localhost:8000"):
        # Kết nối với Vector DB
        self.vector_db = VectorDBConnection(uri=vector_db_uri)
        self.vector_db.connect()

    def calculate_hit_rate(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        """
        Tính toán xem ít nhất 1 trong expected_ids có nằm trong top_k của retrieved_ids không.
        """
        if not expected_ids or not retrieved_ids:
            return 0.0
            
        top_retrieved = retrieved_ids[:top_k]
        hit = any(doc_id in top_retrieved for doc_id in expected_ids)
        return 1.0 if hit else 0.0

    def calculate_mrr(self, expected_ids: List[str], retrieved_ids: List[str]) -> float:
        """
        Tính Mean Reciprocal Rank.
        Tìm vị trí đầu tiên của một expected_id trong retrieved_ids.
        MRR = 1 / position (vị trí 1-indexed). Nếu không thấy thì là 0.
        """
        if not expected_ids or not retrieved_ids:
            return 0.0
            
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in expected_ids:
                return 1.0 / (i + 1)
        return 0.0

    def analyze_chunk_errors(self, expected_ids: List[str], retrieved_ids: List[str]) -> Dict:
        """
        Phân tích chunk-level errors.
        - missing_chunks: Các chunk cần thiết nhưng không được tìm thấy.
        - noise_chunks: Các chunk được trả về nhưng không cần thiết.
        """
        expected_set = set(expected_ids)
        retrieved_set = set(retrieved_ids)
        
        missing = list(expected_set - retrieved_set)
        noise = list(retrieved_set - expected_set)
        
        return {
            "missing_chunks": missing,
            "noise_chunks": noise,
            "is_perfect_match": len(missing) == 0 and len(noise) == 0
        }

    async def evaluate_batch(self, dataset: List[Dict]) -> Dict:
        """
        Chạy eval cho toàn bộ bộ dữ liệu.
        Dataset cần có trường 'expected_retrieval_ids'.
        """
        total_hit_rate = 0.0
        total_mrr = 0.0
        total_cases = len(dataset)
        error_analysis = []
        
        if total_cases == 0:
            return {"avg_hit_rate": 0.0, "avg_mrr": 0.0, "total_evaluated": 0, "detailed_analysis": []}
        
        for case in dataset:
            expected = case.get("expected_retrieval_ids", [])
            
            # Lấy retrieved_ids nếu đã được chuẩn bị sẵn, nếu không thử query qua Vector DB
            retrieved = case.get("retrieved_ids")
            if retrieved is None:
                question = case.get("question", "")
                # Query thử Vector DB để lấy mock retrieved_ids
                retrieved = await self.vector_db.query(question, top_k=3)
            
            # 1. Tính toán metrics
            hit_rate = self.calculate_hit_rate(expected, retrieved)
            mrr = self.calculate_mrr(expected, retrieved)
            
            total_hit_rate += hit_rate
            total_mrr += mrr
            
            # 2. Phân tích lỗi (Chunk-level)
            chunk_errors = self.analyze_chunk_errors(expected, retrieved)
            
            error_analysis.append({
                "question": case.get("question"),
                "expected_ids": expected,
                "retrieved_ids": retrieved,
                "hit_rate": hit_rate,
                "mrr": mrr,
                "errors": chunk_errors
            })

        avg_hit_rate = total_hit_rate / total_cases
        avg_mrr = total_mrr / total_cases

        return {
            "avg_hit_rate": avg_hit_rate,
            "avg_mrr": avg_mrr,
            "total_evaluated": total_cases,
            "detailed_analysis": error_analysis
        }
