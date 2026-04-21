"""
engine/runner.py
BenchmarkRunner — chạy toàn bộ evaluation pipeline cho một dataset.

Pipeline mỗi test case:
  1. Agent.query(question) → answer + contexts
  2. RetrievalEvaluator.score(case, response) → ragas metrics (hit_rate, mrr, faithfulness, relevancy)
  3. LLMJudge.evaluate_multi_judge(q, a, gt) → multi-judge consensus scores
  4. Tổng hợp thành dict chuẩn cho RegressionGate
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """
    Orchestrator chạy benchmark song song.
    Chấp nhận bất kỳ agent, evaluator, judge nào miễn chúng
    expose đúng interface sau:
      - agent.query(question: str) -> Dict (keys: answer, contexts, ...)
      - evaluator.score(case: Dict, response: Dict) -> Dict (keys: faithfulness, relevancy, retrieval)
      - judge.evaluate_multi_judge(q, a, gt) -> Dict (keys: final_score, agreement_rate, ...)
    """

    def __init__(self, agent, evaluator, judge, max_concurrency: int = 5):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge
        # Semaphore để kiểm soát số request song song → tránh rate-limit
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def run_single_test(self, test_case: Dict) -> Dict:
        """Chạy pipeline đầy đủ cho 1 test case."""
        async with self._semaphore:
            return await self._run_single_test_inner(test_case)

    async def _run_single_test_inner(self, test_case: Dict) -> Dict:
        question: str = test_case.get("question", "")
        expected_answer: str = test_case.get("expected_answer", "")
        expected_ids: List[str] = test_case.get("expected_retrieval_ids", [])

        start_time = time.perf_counter()
        agent_answer = ""
        response: Dict[str, Any] = {}

        # ── 1. Gọi Agent ──────────────────────────────────────────
        try:
            response = await self.agent.query(question)
            agent_answer = response.get("answer", "")
        except Exception as e:
            logger.error(f"[Runner] Agent lỗi với câu hỏi '{question[:50]}': {e}")
            agent_answer = f"[AGENT ERROR] {e}"
            response = {"answer": agent_answer, "contexts": [], "retrieved_ids": []}

        latency = time.perf_counter() - start_time

        # ── 2. Retrieval + RAGAS Metrics ─────────────────────────
        ragas_scores: Dict[str, Any] = {
            "faithfulness": 0.0,
            "relevancy": 0.0,
            "retrieval": {"hit_rate": 0.0, "mrr": 0.0},
        }
        try:
            ragas_scores = await self.evaluator.score(test_case, response)
        except Exception as e:
            logger.error(f"[Runner] Evaluator lỗi: {e}")

        # ── 3. Multi-Judge Consensus ──────────────────────────────
        judge_result: Dict[str, Any] = {
            "final_score": 0.0,
            "agreement_rate": 0.0,
            "reasoning": f"[JUDGE ERROR] Chưa có kết quả",
            "resolution_method": "Error",
            "total_cost_usd": 0.0,
        }
        try:
            judge_result = await self.judge.evaluate_multi_judge(
                question, agent_answer, expected_answer
            )
        except Exception as e:
            logger.error(f"[Runner] Judge lỗi: {e}")

        # ── 4. Tổng hợp kết quả ───────────────────────────────────
        final_score = judge_result.get("final_score", 0.0)
        status = "pass" if final_score >= 3.0 else "fail"

        return {
            # Metadata
            "test_case": question,
            "expected_answer": expected_answer,
            "agent_response": agent_answer,
            "expected_retrieval_ids": expected_ids,
            "latency": round(latency, 4),
            "status": status,
            # RAGAS / Retrieval metrics
            "ragas": ragas_scores,
            # Judge metrics
            "judge": {
                "final_score": final_score,
                "agreement_rate": judge_result.get("agreement_rate", 0.0),
                "resolution_method": judge_result.get("resolution_method", ""),
                "reasoning": judge_result.get("reasoning", ""),
                "individual_scores": judge_result.get("individual_scores", []),
                "total_cost_usd": judge_result.get("total_cost_usd", 0.0),
            },
        }

    async def run_all(self, dataset: List[Dict], batch_size: int = 5) -> List[Dict]:
        """
        Chạy toàn bộ dataset, xử lý song song theo batch.

        batch_size: số case chạy đồng thời (kiểm soát rate-limit API).
        return_exceptions=True: đảm bảo 1 case lỗi không làm gãy cả batch.
        """
        all_results: List[Dict] = []
        total = len(dataset)
        completed = 0

        for i in range(0, total, batch_size):
            batch = dataset[i : i + batch_size]
            tasks = [self.run_single_test(case) for case in batch]

            raw = await asyncio.gather(*tasks, return_exceptions=True)

            for j, item in enumerate(raw):
                if isinstance(item, Exception):
                    logger.error(f"[Runner] Case {i+j} gặp exception: {item}")
                    # Tạo placeholder result để không mất case
                    all_results.append({
                        "test_case": batch[j].get("question", f"case_{i+j}"),
                        "expected_answer": batch[j].get("expected_answer", ""),
                        "agent_response": f"[EXCEPTION] {item}",
                        "expected_retrieval_ids": batch[j].get("expected_retrieval_ids", []),
                        "latency": 0.0,
                        "status": "fail",
                        "ragas": {"faithfulness": 0.0, "relevancy": 0.0, "retrieval": {"hit_rate": 0.0, "mrr": 0.0}},
                        "judge": {"final_score": 0.0, "agreement_rate": 0.0, "resolution_method": "Error",
                                  "reasoning": str(item), "individual_scores": [], "total_cost_usd": 0.0},
                    })
                else:
                    all_results.append(item)

            completed += len(batch)
            logger.info(f"[Runner] Tiến độ: {completed}/{total} cases ({100*completed//total}%)")
            print(f"  📊 Tiến độ: {completed}/{total} ({100*completed//total}%)")

            # Delay nhỏ giữa các batch để tránh rate-limit
            if i + batch_size < total:
                await asyncio.sleep(1)

        return all_results
