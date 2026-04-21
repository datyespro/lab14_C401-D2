import json
import os
import time
from typing import List, Dict


class RegressionGate:
    def __init__(self):
        self.thresholds = {
            "quality_delta_min": 0.05,
            "min_hit_rate": 0.80,
            "min_mrr": 0.60,
            "min_agreement_rate": 0.70,
            "max_avg_latency_ms": 3000,
            "max_cost_ratio": 1.5,
        }

    def _avg_metric(self, results: List[Dict], key_path: str) -> float:
        total = 0
        for r in results:
            val = r
            for k in key_path.split("."):
                val = val[k]
            total += val
        return total / len(results) if results else 0

    def _build_summary(self, version: str, results: List[Dict]) -> Dict:
        total = len(results)
        if total == 0:
            return {"version": version, "total": 0, "metrics": {}}

        metrics = {
            "avg_score": self._avg_metric(results, "judge.final_score"),
            "hit_rate": self._avg_metric(results, "ragas.retrieval.hit_rate"),
            "mrr": self._avg_metric(results, "ragas.retrieval.mrr"),
            "agreement_rate": self._avg_metric(results, "judge.agreement_rate"),
            "avg_latency_ms": self._avg_metric(results, "latency") * 1000,
            "faithfulness": self._avg_metric(results, "ragas.faithfulness"),
            "relevancy": self._avg_metric(results, "ragas.relevancy"),
            "pass_rate": sum(1 for r in results if r.get("status") == "pass") / total,
        }
        return {"version": version, "total": total, "metrics": metrics}

    def _estimate_cost(self, num_cases: int) -> Dict:
        GPT_INPUT, GPT_OUTPUT = 150, 80
        CLAUDE_INPUT, CLAUDE_OUTPUT = 150, 80
        cost = (num_cases * GPT_INPUT * 0.03 / 1000 + num_cases * GPT_OUTPUT * 0.06 / 1000 +
                num_cases * CLAUDE_INPUT * 0.003 / 1000 + num_cases * CLAUDE_OUTPUT * 0.015 / 1000)
        return {
            "total_cost_usd": round(cost, 6),
            "cost_per_case_usd": round(cost / num_cases, 6) if num_cases else 0,
            "total_tokens": num_cases * (GPT_INPUT + GPT_OUTPUT + CLAUDE_INPUT + CLAUDE_OUTPUT),
        }

    def _compute_delta(self, v1: float, v2: float, higher_is_better: bool = True) -> Dict:
        delta = v2 - v1
        pct = (delta / v1 * 100) if v1 != 0 else (100.0 if v2 > 0 else 0.0)
        if abs(delta) < 1e-9:
            direction = "unchanged"
        elif (higher_is_better and delta > 0) or (not higher_is_better and delta < 0):
            direction = "improved"
        else:
            direction = "degraded"
        return {"v1": v1, "v2": v2, "delta": round(delta, 4), "pct": round(pct, 2), "direction": direction}

    def compare(self, v1_results: List[Dict], v2_results: List[Dict]) -> Dict:
        v1_sum = self._build_summary("Agent_V1_Base", v1_results)
        v2_sum = self._build_summary("Agent_V2_Optimized", v2_results)

        m1, m2 = v1_sum["metrics"], v2_sum["metrics"]
        deltas = {
            "avg_score": self._compute_delta(m1.get("avg_score", 0), m2.get("avg_score", 0)),
            "hit_rate": self._compute_delta(m1.get("hit_rate", 0), m2.get("hit_rate", 0)),
            "mrr": self._compute_delta(m1.get("mrr", 0), m2.get("mrr", 0)),
            "agreement_rate": self._compute_delta(m1.get("agreement_rate", 0), m2.get("agreement_rate", 0)),
            "avg_latency_ms": self._compute_delta(m1.get("avg_latency_ms", 0), m2.get("avg_latency_ms", 0), higher_is_better=False),
            "faithfulness": self._compute_delta(m1.get("faithfulness", 0), m2.get("faithfulness", 0)),
            "relevancy": self._compute_delta(m1.get("relevancy", 0), m2.get("relevancy", 0)),
            "pass_rate": self._compute_delta(m1.get("pass_rate", 0), m2.get("pass_rate", 0)),
        }

        v1_cost = self._estimate_cost(len(v1_results))
        v2_cost = self._estimate_cost(len(v2_results))
        cost_ratio = v2_cost["total_cost_usd"] / v1_cost["total_cost_usd"] if v1_cost["total_cost_usd"] > 0 else 0

        return {
            "v1_summary": v1_sum,
            "v2_summary": v2_sum,
            "deltas": deltas,
            "cost_v1": v1_cost,
            "cost_v2": v2_cost,
            "cost_ratio": round(cost_ratio, 4),
        }

    def evaluate_gate(self, comparison: Dict) -> Dict:
        m = comparison["v2_summary"]["metrics"]
        t = self.thresholds
        reasons = []
        blockers = []

        if m.get("hit_rate", 0) < t["min_hit_rate"]:
            blockers.append(f"Hit Rate {m['hit_rate']:.3f} < {t['min_hit_rate']} (BLOCK)")
        else:
            reasons.append(f"Hit Rate: {m['hit_rate']:.3f} >= {t['min_hit_rate']} OK")

        if m.get("mrr", 0) < t["min_mrr"]:
            blockers.append(f"MRR {m['mrr']:.3f} < {t['min_mrr']} (BLOCK)")
        else:
            reasons.append(f"MRR: {m['mrr']:.3f} >= {t['min_mrr']} OK")

        score_delta = comparison["deltas"]["avg_score"]["delta"]
        if score_delta < t["quality_delta_min"]:
            blockers.append(f"Score Delta {score_delta:+.3f} < {t['quality_delta_min']} (BLOCK)")
        else:
            reasons.append(f"Score Delta: {score_delta:+.3f} >= {t['quality_delta_min']} OK")

        if m.get("avg_latency_ms", 0) > t["max_avg_latency_ms"]:
            blockers.append(f"Latency {m['avg_latency_ms']:.0f}ms > {t['max_avg_latency_ms']}ms (BLOCK)")
        else:
            reasons.append(f"Latency: {m['avg_latency_ms']:.0f}ms < {t['max_avg_latency_ms']}ms OK")

        if comparison["cost_ratio"] > t["max_cost_ratio"]:
            blockers.append(f"Cost ratio {comparison['cost_ratio']:.2f}x > {t['max_cost_ratio']}x (BLOCK)")

        if blockers:
            decision = "BLOCK"
            all_reasons = reasons + blockers
        else:
            decision = "APPROVE"
            all_reasons = reasons

        return {"decision": decision, "reasons": all_reasons, "blockers": blockers}

    def run(self, v1_results: List[Dict], v2_results: List[Dict]) -> Dict:
        comparison = self.compare(v1_results, v2_results)
        gate = self.evaluate_gate(comparison)

        report = {
            "metadata": {
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "v1_version": "Agent_V1_Base",
                "v2_version": "Agent_V2_Optimized",
                "thresholds": self.thresholds,
            },
            "v1_summary": comparison["v1_summary"],
            "v2_summary": comparison["v2_summary"],
            "deltas": comparison["deltas"],
            "cost_comparison": {
                "v1_cost_usd": comparison["cost_v1"]["total_cost_usd"],
                "v2_cost_usd": comparison["cost_v2"]["total_cost_usd"],
                "cost_per_case_v2": comparison["cost_v2"]["cost_per_case_usd"],
                "total_tokens": comparison["cost_v2"]["total_tokens"],
                "cost_ratio": comparison["cost_ratio"],
            },
            "gate_decision": gate["decision"],
            "gate_reasons": gate["reasons"],
        }

        os.makedirs("reports", exist_ok=True)
        with open("reports/regression_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self._print_report(report)
        return report

    def _print_report(self, report: Dict):
        print("\n" + "=" * 60)
        print("REGRESSION REPORT SUMMARY")
        print("=" * 60)
        print(f"{'Metric':<20} {'V1':>10} {'V2':>10} {'Delta':>10}")
        print("-" * 60)
        for key, d in report["deltas"].items():
            print(f"{key:<20} {d['v1']:>10.4f} {d['v2']:>10.4f} {d['delta']:>+10.4f}")
        print("-" * 60)
        cc = report["cost_comparison"]
        print(f"Cost V1: ${cc['v1_cost_usd']:.4f} | V2: ${cc['v2_cost_usd']:.4f} | Ratio: {cc['cost_ratio']:.2f}x")
        print("=" * 60)
        print(f"GATE DECISION: {report['gate_decision']}")
        print("Reasons:", ", ".join(report["gate_reasons"][:3]))
        print()


def run_regression_gate(v1_results: List[Dict], v2_results: List[Dict]) -> Dict:
    gate = RegressionGate()
    return gate.run(v1_results, v2_results)


if __name__ == "__main__":
    mock_v1 = [
        {"test_case": f"Q{i}", "judge": {"final_score": 3.5 + i*0.01, "agreement_rate": 0.75},
         "ragas": {"faithfulness": 0.76, "relevancy": 0.71, "retrieval": {"hit_rate": 0.82, "mrr": 0.65}},
         "latency": 0.85, "status": "pass" if i < 40 else "fail"}
        for i in range(50)
    ]
    mock_v2 = [
        {"test_case": f"Q{i}", "judge": {"final_score": 3.9 + i*0.01, "agreement_rate": 0.83},
         "ragas": {"faithfulness": 0.85, "relevancy": 0.78, "retrieval": {"hit_rate": 0.90, "mrr": 0.75}},
         "latency": 0.65, "status": "pass" if i < 45 else "fail"}
        for i in range(50)
    ]
    run_regression_gate(mock_v1, mock_v2)
