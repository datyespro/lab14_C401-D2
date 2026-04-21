import asyncio
import json
import os
import time
from statistics import mean

from agent.main_agent import MainAgent
from engine.retrieval_eval import RetrievalEvaluator
from engine.llm_judge import LLMJudge


async def ensure_golden_set():
    path = "data/golden_set.jsonl"
    if not os.path.exists(path):
        print("Golden set not found — generating with data/synthetic_gen.py")
        # call the script to generate the golden set
        os.system("python data/synthetic_gen.py")
    return path


def load_golden(path):
    dataset = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                dataset.append(json.loads(line))
    return dataset


async def run_tests(dataset, concurrency: int = 8):
    agent = MainAgent()
    retriever = RetrievalEvaluator()
    judge = LLMJudge()

    semaphore = asyncio.Semaphore(concurrency)

    async def run_case(case):
        async with semaphore:
            start = time.perf_counter()
            resp = await agent.query(case.get("question", ""))
            latency = time.perf_counter() - start

            # retrieved IDs from agent metadata (best-effort)
            retrieved = resp.get("metadata", {}).get("sources", [])
            expected_ids = case.get("expected_retrieval_ids", [])

            hit = retriever.calculate_hit_rate(expected_ids, retrieved, top_k=3)
            mrr = retriever.calculate_mrr(expected_ids, retrieved)

            judge_res = await judge.evaluate_multi_judge(
                case.get("question", ""),
                resp.get("answer", ""),
                case.get("expected_answer", "")
            )

            status = "pass" if judge_res.get("final_score", 0) >= 3 else "fail"

            return {
                "question": case.get("question"),
                "expected_answer": case.get("expected_answer"),
                "agent_answer": resp.get("answer"),
                "latency": latency,
                "hit": hit,
                "mrr": mrr,
                "judge": judge_res,
                "status": status
            }

    tasks = [asyncio.create_task(run_case(c)) for c in dataset]
    results = await asyncio.gather(*tasks)
    return results


def summarize(results):
    total = len(results)
    avg_score = mean([r["judge"]["final_score"] for r in results]) if results else 0
    avg_hit = mean([r["hit"] for r in results]) if results else 0
    avg_mrr = mean([r["mrr"] for r in results]) if results else 0
    avg_agreement = mean([r["judge"].get("agreement_rate", 0) for r in results]) if results else 0

    summary = {
        "metadata": {"total": total, "version": "v1.0-integration"},
        "metrics": {
            "avg_score": avg_score,
            "hit_rate": avg_hit,
            "mrr": avg_mrr,
            "agreement_rate": avg_agreement,
        }
    }
    return summary


def save_reports(summary, results):
    os.makedirs("reports", exist_ok=True)
    with open("reports/summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open("reports/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False, indent=2)


def write_failure_analysis(results):
    os.makedirs("analysis", exist_ok=True)
    fails = [r for r in results if r["status"] == "fail"]
    with open("analysis/failure_analysis.md", "w", encoding="utf-8") as f:
        f.write("# Failure Analysis (Top issues)\n\n")
        f.write(f"Total failures: {len(fails)}\n\n")

        # Simple clustering: group by whether agent answer contains word 'mẫu'
        clusters = {}
        for r in fails:
            key = "contains_sample_marker" if "mẫu" in (r["agent_answer"] or "") else "other"
            clusters.setdefault(key, []).append(r)

        for k, items in clusters.items():
            f.write(f"## Cluster: {k} (count: {len(items)})\n\n")
            # 5 Whys placeholder per cluster
            f.write("### 5 Whys (example)\n")
            f.write("1. Why did the agent fail? Because answer was generic.\n")
            f.write("2. Why generic? Because retrieval returned low-quality context.\n")
            f.write("3. Why poor retrieval? Because chunking missed the key sentence.\n")
            f.write("4. Why chunking failed? Because ingestion metadata incomplete.\n")
            f.write("5. Why ingestion incomplete? Need better pipeline checks.\n\n")


async def main():
    path = await ensure_golden_set()
    dataset = load_golden(path)
    start = time.perf_counter()
    results = await run_tests(dataset)
    total_time = time.perf_counter() - start

    summary = summarize(results)
    summary["metadata"]["total_time_s"] = total_time

    save_reports(summary, results)
    write_failure_analysis(results)

    print(f"Completed {len(results)} tests in {total_time:.2f}s. Reports saved to reports/.")


if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import json
import os
import time
from engine.runner import BenchmarkRunner
from agent.main_agent import MainAgent

# Giả lập các components Expert
class ExpertEvaluator:
    async def score(self, case, resp): 
        # Giả lập tính toán Hit Rate và MRR
        return {
            "faithfulness": 0.9, 
            "relevancy": 0.8,
            "retrieval": {"hit_rate": 1.0, "mrr": 0.5}
        }

class MultiModelJudge:
    async def evaluate_multi_judge(self, q, a, gt): 
        return {
            "final_score": 4.5, 
            "agreement_rate": 0.8,
            "reasoning": "Cả 2 model đồng ý đây là câu trả lời tốt."
        }

async def run_benchmark_with_results(agent_version: str):
    print(f"🚀 Khởi động Benchmark cho {agent_version}...")

    if not os.path.exists("data/golden_set.jsonl"):
        print("❌ Thiếu data/golden_set.jsonl. Hãy chạy 'python data/synthetic_gen.py' trước.")
        return None, None

    with open("data/golden_set.jsonl", "r", encoding="utf-8") as f:
        dataset = [json.loads(line) for line in f if line.strip()]

    if not dataset:
        print("❌ File data/golden_set.jsonl rỗng. Hãy tạo ít nhất 1 test case.")
        return None, None

    runner = BenchmarkRunner(MainAgent(), ExpertEvaluator(), MultiModelJudge())
    results = await runner.run_all(dataset)

    total = len(results)
    summary = {
        "metadata": {"version": agent_version, "total": total, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")},
        "metrics": {
            "avg_score": sum(r["judge"]["final_score"] for r in results) / total,
            "hit_rate": sum(r["ragas"]["retrieval"]["hit_rate"] for r in results) / total,
            "agreement_rate": sum(r["judge"]["agreement_rate"] for r in results) / total
        }
    }
    return results, summary

async def run_benchmark(version):
    _, summary = await run_benchmark_with_results(version)
    return summary

async def main():
    v1_summary = await run_benchmark("Agent_V1_Base")
    
    # Giả lập V2 có cải tiến (để test logic)
    v2_results, v2_summary = await run_benchmark_with_results("Agent_V2_Optimized")
    
    if not v1_summary or not v2_summary:
        print("❌ Không thể chạy Benchmark. Kiểm tra lại data/golden_set.jsonl.")
        return

    print("\n📊 --- KẾT QUẢ SO SÁNH (REGRESSION) ---")
    delta = v2_summary["metrics"]["avg_score"] - v1_summary["metrics"]["avg_score"]
    print(f"V1 Score: {v1_summary['metrics']['avg_score']}")
    print(f"V2 Score: {v2_summary['metrics']['avg_score']}")
    print(f"Delta: {'+' if delta >= 0 else ''}{delta:.2f}")

    os.makedirs("reports", exist_ok=True)
    with open("reports/summary.json", "w", encoding="utf-8") as f:
        json.dump(v2_summary, f, ensure_ascii=False, indent=2)
    with open("reports/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(v2_results, f, ensure_ascii=False, indent=2)

    if delta > 0:
        print("✅ QUYẾT ĐỊNH: CHẤP NHẬN BẢN CẬP NHẬT (APPROVE)")
    else:
        print("❌ QUYẾT ĐỊNH: TỪ CHỐI (BLOCK RELEASE)")

if __name__ == "__main__":
    asyncio.run(main())
