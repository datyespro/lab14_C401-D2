"""
main.py — AI Evaluation Factory (Lab 14)

Pipeline:
  1. Load Golden Dataset từ data/golden_set.jsonl
  2. Chạy BenchmarkRunner (Async) với:
       - agent.query()            → MainAgent
       - evaluator.score()        → RetrievalEvaluator (TF-IDF / Real VectorDB)
       - judge.evaluate_multi_judge() → LLMJudge (GPT + Gemini)
  3. Chạy V1 và V2 (giả lập cải tiến)
  4. Đưa kết quả qua RegressionGate → APPROVE / BLOCK
  5. Xuất:
       - reports/summary.json
       - reports/benchmark_results.json
       - reports/regression_report.json
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Fix Windows console Unicode
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Imports — modules của team
# ──────────────────────────────────────────────────────────

from agent.main_agent import MainAgent
from engine.runner import BenchmarkRunner
from engine.retrieval_eval import RetrievalEvaluator
from engine.llm_judge import LLMJudge
from engine.regression_gate import RegressionGate


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def load_dataset(path: str = "data/golden_set.jsonl") -> Optional[List[Dict]]:
    """Load golden dataset. Trả về None nếu file không tồn tại hoặc rỗng."""
    if not os.path.exists(path):
        logger.error("❌ Thiếu %s. Hãy chạy 'python data/synthetic_gen.py' trước.", path)
        return None

    dataset = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    dataset.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning("Bỏ qua dòng lỗi JSON: %s", e)

    if not dataset:
        logger.error("❌ File %s rỗng. Hãy tạo ít nhất 1 test case.", path)
        return None

    logger.info("✅ Đã load %d test cases từ %s", len(dataset), path)
    return dataset


def build_summary(version: str, results: List[Dict]) -> Dict:
    """Tổng hợp metrics tổng quan từ danh sách kết quả."""
    total = len(results)
    if total == 0:
        return {"metadata": {"version": version, "total": 0}, "metrics": {}}

    def avg(key_fn):
        vals = []
        for r in results:
            try:
                vals.append(key_fn(r))
            except (KeyError, TypeError):
                vals.append(0.0)
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    pass_count = sum(1 for r in results if r.get("status") == "pass")
    total_cost = sum(
        r.get("judge", {}).get("total_cost_usd", 0.0) for r in results
    )

    return {
        "metadata": {
            "version": version,
            "total": total,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "metrics": {
            "avg_score":        avg(lambda r: r["judge"]["final_score"]),
            "hit_rate":         avg(lambda r: r["ragas"]["retrieval"]["hit_rate"]),
            "mrr":              avg(lambda r: r["ragas"]["retrieval"]["mrr"]),
            "faithfulness":     avg(lambda r: r["ragas"]["faithfulness"]),
            "relevancy":        avg(lambda r: r["ragas"]["relevancy"]),
            "agreement_rate":   avg(lambda r: r["judge"]["agreement_rate"]),
            "avg_latency_ms":   avg(lambda r: r["latency"]) * 1000,
            "pass_rate":        round(pass_count / total, 4),
            "total_cost_usd":   round(total_cost, 6),
        },
    }


def save_reports(results: List[Dict], summary: Dict, regression_report: Optional[Dict] = None):
    """Lưu tất cả reports ra thư mục reports/."""
    Path("reports").mkdir(exist_ok=True)

    with open("reports/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("📁 Đã lưu reports/benchmark_results.json")

    # Merge regression report vào summary nếu có
    if regression_report:
        summary["regression"] = {
            "gate_decision": regression_report.get("gate_decision"),
            "gate_reasons": regression_report.get("gate_reasons", []),
            "deltas": regression_report.get("deltas", {}),
            "cost_comparison": regression_report.get("cost_comparison", {}),
        }

    with open("reports/summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info("📁 Đã lưu reports/summary.json")


# ──────────────────────────────────────────────────────────
# Core benchmark function
# ──────────────────────────────────────────────────────────

async def run_benchmark(
    version: str,
    dataset: List[Dict],
    evaluator: RetrievalEvaluator,
    judge: LLMJudge,
    batch_size: int = 5,
) -> Tuple[List[Dict], Dict]:
    """
    Chạy toàn bộ benchmark cho một phiên bản agent.
    Trả về (results, summary).
    """
    print(f"\n🚀 [{version}] Bắt đầu benchmark {len(dataset)} test cases...")
    t0 = time.perf_counter()

    agent = MainAgent()
    runner = BenchmarkRunner(agent, evaluator, judge, max_concurrency=batch_size)
    results = await runner.run_all(dataset, batch_size=batch_size)

    elapsed = time.perf_counter() - t0
    summary = build_summary(version, results)
    m = summary["metrics"]

    print(f"\n✅ [{version}] Hoàn thành trong {elapsed:.1f}s")
    print(f"   Score: {m.get('avg_score', 0):.3f} | "
          f"Hit Rate: {m.get('hit_rate', 0):.3f} | "
          f"MRR: {m.get('mrr', 0):.3f} | "
          f"Agreement: {m.get('agreement_rate', 0):.3f} | "
          f"Pass Rate: {m.get('pass_rate', 0):.1%}")

    return results, summary


# ──────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────

async def main():
    print("=" * 70)
    print("AI EVALUATION FACTORY -- Lab Day 14")
    print("=" * 70)

    # ── 1. Load dataset ────────────────────────────────────────────
    dataset = load_dataset("data/golden_set.jsonl")
    if dataset is None:
        return

    # ── 2. Khoi tao modules ──────────────────────────────────────
    print("\n[*] Initializing modules...")
    evaluator = RetrievalEvaluator()

    judge = LLMJudge(gpt_model_1="gpt-4o-mini", gpt_model_2="gpt-4o")
    if not judge.judges:
        logger.warning("[!] No Judge initialized. Check API keys in .env")

    # ── 3. Chạy V1 (baseline) ─────────────────────────────────────
    v1_results, v1_summary = await run_benchmark(
        version="Agent_V1_Base",
        dataset=dataset,
        evaluator=evaluator,
        judge=judge,
        batch_size=5,
    )

    # ── 4. Chạy V2 (mimic improved agent) ─────────────────────────
    # Trong thực tế: thay MainAgent() bằng phiên bản agent mới.
    # Ở đây dùng lại cùng dataset để demo Regression Gate logic.
    v2_results, v2_summary = await run_benchmark(
        version="Agent_V2_Optimized",
        dataset=dataset,
        evaluator=evaluator,
        judge=judge,
        batch_size=5,
    )

    # ── 5. Regression Gate ────────────────────────────────────────
    print("\n" + "=" * 70)
    print("REGRESSION GATE ANALYSIS")
    print("=" * 70)

    gate = RegressionGate()
    regression_report = gate.run(v1_results, v2_results)

    decision = regression_report.get("gate_decision", "UNKNOWN")
    blockers = regression_report.get("gate_reasons", [])

    print(f"\nGATE DECISION: [{decision}]")
    if decision == "APPROVE":
        print("   V2 passed Regression Gate -- ACCEPT UPDATE")
    else:
        print("   V2 FAILED -- BLOCK RELEASE")
        if blockers:
            print("   Reasons:")
            for b in blockers:
                print(f"     - {b}")

    # ── 6. Chi phí Judge ──────────────────────────────────────────
    cost_summary = judge.get_cost_summary()
    total_usd = cost_summary.get("total_cost_usd", 0)
    total_calls = cost_summary.get("total_api_calls", 0)
    cost_per_eval = cost_summary.get("cost_per_eval", 0)
    print(f"\nCost summary:")
    print(f"   Total: ${total_usd:.4f} | API calls: {total_calls} | Cost/call: ${cost_per_eval:.6f}")

    # ── 7. Lưu reports ────────────────────────────────────────────
    save_reports(v2_results, v2_summary, regression_report)
    print("\nReports saved:")
    print("   - reports/summary.json")
    print("   - reports/benchmark_results.json")
    print("   - reports/regression_report.json")
    print("\nDone! Run 'python check_lab.py' to verify before submission.")
    print("=" * 70)


# ──────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
