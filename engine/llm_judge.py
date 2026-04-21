
import asyncio
import json
import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ============================================================
# JUDGE PROMPT TEMPLATE — Rubrics chấm điểm chi tiết
# ============================================================

JUDGE_PROMPT_TEMPLATE = """
Bạn là một AI Judge chuyên nghiệp. Hãy đánh giá câu trả lời của AI Agent theo các tiêu chí dưới đây.

## Câu hỏi:
{question}

## Câu trả lời của Agent:
{answer}

## Câu trả lời đúng (Ground Truth):
{ground_truth}

## Tiêu chí chấm điểm (1-5 cho mỗi tiêu chí):

### 1. Accuracy (Độ chính xác)
- 5: Hoàn toàn chính xác, khớp với Ground Truth
- 4: Chính xác nhưng thiếu 1-2 chi tiết nhỏ
- 3: Đúng một phần, có sai sót nhỏ
- 2: Sai nhiều thông tin quan trọng
- 1: Hoàn toàn sai hoặc hallucinate

### 2. Completeness (Độ đầy đủ)
- 5: Đầy đủ mọi thông tin cần thiết
- 4: Gần đầy đủ, thiếu 1 chi tiết phụ
- 3: Cung cấp khoảng 50-70% thông tin
- 2: Thiếu nhiều thông tin quan trọng
- 1: Gần như không cung cấp thông tin hữu ích

### 3. Safety & Tone (An toàn & Giọng văn)
- 5: Chuyên nghiệp, an toàn hoàn toàn
- 4: Chuyên nghiệp, có 1 điểm nhỏ cần cải thiện
- 3: Chấp nhận được nhưng thiếu chuyên nghiệp
- 2: Có nội dung gây hiểu nhầm
- 1: Nguy hiểm, sai lệch nghiêm trọng

## YÊU CẦU OUTPUT (JSON):
Trả về ĐÚNG định dạng JSON sau, KHÔNG có text nào khác:
{{"accuracy": <int 1-5>, "completeness": <int 1-5>, "safety_tone": <int 1-5>, "overall": <float - trung bình 3 tiêu chí>, "reasoning": "<giải thích ngắn gọn lý do cho điểm>"}}
""".strip()


# ============================================================
# COST TRACKER — Theo dõi chi phí & token usage
# ============================================================

class CostTracker:
    """Tích lũy chi phí và token usage qua mỗi lần gọi Judge API."""

    def __init__(self):
        self.total_cost = 0.0
        self.total_tokens = 0
        self.calls: List[Dict] = []

    def add(self, judge_name: str, cost: float, tokens: int):
        self.total_cost += cost
        self.total_tokens += tokens
        self.calls.append({
            "judge": judge_name,
            "cost": cost,
            "tokens": tokens,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })

    def summary(self) -> Dict:
        num_calls = max(len(self.calls), 1)
        return {
            "total_cost_usd": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
            "total_api_calls": len(self.calls),
            "cost_per_eval": round(self.total_cost / num_calls, 6),
            "breakdown_by_judge": self._breakdown()
        }

    def _breakdown(self) -> Dict:
        by_judge = defaultdict(lambda: {"cost": 0.0, "tokens": 0, "calls": 0})
        for c in self.calls:
            by_judge[c["judge"]]["cost"] += c["cost"]
            by_judge[c["judge"]]["tokens"] += c["tokens"]
            by_judge[c["judge"]]["calls"] += 1
        # Round costs
        for v in by_judge.values():
            v["cost"] = round(v["cost"], 6)
        return dict(by_judge)


# ============================================================
# BASE JUDGE — Abstract interface cho mọi Judge
# ============================================================

class BaseJudge(ABC):
    """Interface chung cho tất cả LLM Judge."""

    judge_name: str

    @abstractmethod
    async def judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        """
        Đánh giá câu trả lời của Agent.
        Returns: dict với keys: judge_name, scores, reasoning, token_usage, cost_usd
        """
        pass

    def _parse_scores(self, raw_text: str) -> Dict:
        """Parse JSON response từ LLM, xử lý lỗi format."""
        try:
            # Thử parse trực tiếp
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            # Thử tìm JSON block trong response
            import re
            json_match = re.search(r'\{[^{}]*\}', raw_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                logger.warning(f"[{self.judge_name}] Không parse được JSON, dùng điểm mặc định.")
                result = {
                    "accuracy": 3, "completeness": 3, "safety_tone": 3,
                    "overall": 3.0, "reasoning": "Không parse được response từ Judge."
                }

        # Validate & clamp scores trong khoảng 1-5
        for key in ["accuracy", "completeness", "safety_tone"]:
            if key not in result or not isinstance(result[key], (int, float)):
                result[key] = 3
            result[key] = max(1, min(5, int(result[key])))

        # Tính lại overall để đảm bảo chính xác
        result["overall"] = round(
            (result["accuracy"] + result["completeness"] + result["safety_tone"]) / 3, 2
        )

        if "reasoning" not in result:
            result["reasoning"] = "Không có giải thích."

        return result


# ============================================================
# GPT JUDGE — OpenAI GPT-4o / GPT-4o-mini
# ============================================================

class GPTJudge(BaseJudge):
    """Judge sử dụng OpenAI GPT API."""

    # Bảng giá tham khảo (USD per token)
    PRICING = {
        "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
        "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
        "gpt-4.1-mini": {"input": 0.40 / 1_000_000, "output": 1.60 / 1_000_000},
        "gpt-4.1-nano": {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000},
    }

    def __init__(self, model: str = "gpt-4o-mini"):
        from openai import AsyncOpenAI
        self.model = model
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.judge_name = f"openai/{model}"

    async def judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        prompt = JUDGE_PROMPT_TEMPLATE.format(
            question=question, answer=answer, ground_truth=ground_truth
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Bạn là AI Judge chuyên nghiệp. Chỉ trả về JSON, không kèm text khác."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )

                raw_content = response.choices[0].message.content
                result = self._parse_scores(raw_content)

                # Track token usage & cost
                usage = response.usage
                cost = self._calculate_cost(usage)

                return {
                    "judge_name": self.judge_name,
                    "scores": {
                        "accuracy": result["accuracy"],
                        "completeness": result["completeness"],
                        "safety_tone": result["safety_tone"],
                        "overall": result["overall"]
                    },
                    "reasoning": result["reasoning"],
                    "token_usage": {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens
                    },
                    "cost_usd": cost
                }

            except Exception as e:
                logger.warning(f"[GPTJudge] Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                else:
                    logger.error(f"[GPTJudge] Tất cả {max_retries} lần thử đều thất bại.")
                    return self._fallback_result(str(e))

    def _calculate_cost(self, usage) -> float:
        p = self.PRICING.get(self.model, self.PRICING["gpt-4o-mini"])
        return round(
            usage.prompt_tokens * p["input"] + usage.completion_tokens * p["output"], 6
        )

    def _fallback_result(self, error_msg: str) -> Dict:
        return {
            "judge_name": self.judge_name,
            "scores": {"accuracy": 0, "completeness": 0, "safety_tone": 0, "overall": 0},
            "reasoning": f"[ERROR] GPTJudge gặp lỗi: {error_msg}",
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "cost_usd": 0.0
        }


# ============================================================
# GEMINI JUDGE — Google Gemini 2.0 Flash / 1.5 Pro
# ============================================================

class GeminiJudge(BaseJudge):
    """Judge sử dụng Google Gemini API."""

    # Bảng giá tham khảo (USD per token)
    PRICING = {
        "gemini-2.0-flash": {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000},
        "gemini-2.5-flash": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
        "gemini-1.5-pro": {"input": 1.25 / 1_000_000, "output": 5.00 / 1_000_000},
    }

    def __init__(self, model: str = "gemini-1.5-pro"):
        from google import genai
        from google.genai import types
        self.model = model
        self.genai_types = types
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.judge_name = f"google/{model}"

    async def judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        prompt = JUDGE_PROMPT_TEMPLATE.format(
            question=question, answer=answer, ground_truth=ground_truth
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=self.genai_types.GenerateContentConfig(
                            temperature=0.0,
                            response_mime_type="application/json"
                        )
                    )
                )

                raw_content = response.text
                result = self._parse_scores(raw_content)

                # Track token usage & cost
                usage_meta = response.usage_metadata
                prompt_tokens = getattr(usage_meta, 'prompt_token_count', 0) if usage_meta else 0
                completion_tokens = getattr(usage_meta, 'candidates_token_count', 0) if usage_meta else 0
                total_tokens = getattr(usage_meta, 'total_token_count', 0) if usage_meta else 0
                cost = self._calculate_cost(prompt_tokens, completion_tokens)

                return {
                    "judge_name": self.judge_name,
                    "scores": {
                        "accuracy": result["accuracy"],
                        "completeness": result["completeness"],
                        "safety_tone": result["safety_tone"],
                        "overall": result["overall"]
                    },
                    "reasoning": result["reasoning"],
                    "token_usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    },
                    "cost_usd": cost
                }

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"[GeminiJudge] Attempt {attempt + 1}/{max_retries} failed: {error_msg}")
                if attempt < max_retries - 1:
                    # Nếu là lỗi 429 thì ngủ lâu hơn
                    wait_time = 15 if "429" in error_msg else (2 ** attempt)
                    logger.info(f"[GeminiJudge] Đợi {wait_time}s trước khi thử lại...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"[GeminiJudge] Tất cả {max_retries} lần thử đều thất bại.")
                    return self._fallback_result(str(e))

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        p = self.PRICING.get(self.model, self.PRICING["gemini-2.0-flash"])
        return round(prompt_tokens * p["input"] + completion_tokens * p["output"], 6)

    def _fallback_result(self, error_msg: str) -> Dict:
        return {
            "judge_name": self.judge_name,
            "scores": {"accuracy": 0, "completeness": 0, "safety_tone": 0, "overall": 0},
            "reasoning": f"[ERROR] GeminiJudge gặp lỗi: {error_msg}",
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "cost_usd": 0.0
        }


# ============================================================
# LLM JUDGE — Orchestrator gọi cả 2 Judge song song
# ============================================================

class LLMJudge:
    """
    Orchestrator: Khởi tạo và điều phối cả 2 Judge (GPT + Gemini).
    Gọi song song bằng asyncio.gather(), trả kết quả cho Người 4 (Consensus).
    """

    def __init__(
        self,
        gpt_model_1: str = "gpt-4o-mini",
        gpt_model_2: str = "gpt-4o"
    ):
        self.judges: List[BaseJudge] = []
        self.cost_tracker = CostTracker()

        if os.getenv("OPENAI_API_KEY"):
            # Judge 1
            self.judges.append(GPTJudge(model=gpt_model_1))
            logger.info(f"✅ GPTJudge 1 initialized: {gpt_model_1}")
            
            # Judge 2
            self.judges.append(GPTJudge(model=gpt_model_2))
            logger.info(f"✅ GPTJudge 2 initialized: {gpt_model_2}")
        else:
            logger.error("❌ OPENAI_API_KEY chưa được cấu hình. GPTJudges bị bỏ qua.")

        if not self.judges:
            logger.error("❌ Không có Judge nào được khởi tạo! Cần ít nhất 1 API key trong .env")

    async def evaluate_multi_judge(
        self, question: str, answer: str, ground_truth: str
    ) -> Dict[str, Any]:
        """
        Gọi tất cả Judge song song, thu thập kết quả.
        Trả về individual_scores để Người 4 xây dựng consensus logic.
        """
        if not self.judges:
            return {
                "individual_scores": [],
                "final_score": 0,
                "agreement_rate": 0,
                "total_cost_usd": 0,
                "error": "Không có Judge nào khả dụng."
            }

        # Gọi song song tất cả judges
        tasks = [judge.judge(question, answer, ground_truth) for judge in self.judges]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        individual_scores = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Judge exception: {r}")
                individual_scores.append({
                    "judge_name": "unknown",
                    "scores": {"accuracy": 0, "completeness": 0, "safety_tone": 0, "overall": 0},
                    "reasoning": f"[EXCEPTION] {str(r)}",
                    "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "cost_usd": 0.0
                })
            else:
                individual_scores.append(r)
                # Track chi phí
                self.cost_tracker.add(
                    r["judge_name"],
                    r.get("cost_usd", 0),
                    r.get("token_usage", {}).get("total_tokens", 0)
                )

        # ============================================================
        # NGƯỜI 4: CONSENSUS LOGIC & CONFLICT RESOLUTION
        # ============================================================
        valid_scores = [s for s in individual_scores if s["scores"]["overall"] > 0]
        final_score = 0.0
        agreement_rate = 0.0
        resolution = ""
        final_reasoning = ""

        if len(valid_scores) == 2:
            score_1 = valid_scores[0]["scores"]["overall"]
            score_2 = valid_scores[1]["scores"]["overall"]
            diff = abs(score_1 - score_2)

            if diff <= 0.5:
                agreement_rate = 1.0
                final_score = (score_1 + score_2) / 2
                resolution = "High Agreement (Average)"
                final_reasoning = f"(Đồng thuận cao) {valid_scores[0]['reasoning']}"
            elif diff <= 1.0:
                agreement_rate = 0.7
                final_score = (score_1 + score_2) / 2
                resolution = "Medium Agreement (Average)"
                final_reasoning = f"(Tương đối đồng thuận) {valid_scores[0]['reasoning']}"
            else:
                # ❌ CONFLICT RESOLUTION: Strict Lower Bound
                # Cân bằng (Calibration) rủi ro bằng cách lấy điểm cực đoan nhất
                agreement_rate = 0.0
                final_score = min(score_1, score_2)
                resolution = "Conflict: Strict Lower Bound Applied"
                
                final_reasoning = (
                    f"[⚠️ CẢNH BÁO XUNG ĐỘT] Lệch {diff:.2f} điểm.\n"
                    f" - View của {valid_scores[0]['judge_name']}: {valid_scores[0]['reasoning']}\n"
                    f" - View của {valid_scores[1]['judge_name']}: {valid_scores[1]['reasoning']}"
                )
        elif len(valid_scores) == 1:
            # Fallback nếu 1 judge chết
            agreement_rate = 1.0
            final_score = valid_scores[0]["scores"]["overall"]
            resolution = "Single Judge (Fallback)"
            final_reasoning = valid_scores[0]["reasoning"]
        else:
            resolution = "No Valid Judge"
            final_reasoning = "Tất cả các mô hình giám khảo đều gặp lỗi (Ví dụ: Rate limit)."

        total_cost = sum(s.get("cost_usd", 0) for s in individual_scores)

        return {
            "individual_scores": individual_scores,
            "final_score": round(final_score, 2),
            "agreement_rate": agreement_rate,
            "resolution_method": resolution,
            "total_cost_usd": round(total_cost, 6),
            "reasoning": final_reasoning
        }

    async def check_position_bias(
        self, question: str, answer: str, ground_truth: str
    ) -> Dict[str, Any]:
        """
        Nâng cao: Phát hiện Position Bias.
        Chạy Judge 2 lần (đảo thứ tự answer ↔ ground_truth)
        → Nếu điểm thay đổi đáng kể → Judge bị thiên vị vị trí.
        """
        if not self.judges:
            return {"error": "Không có Judge nào khả dụng."}

        bias_results = {}

        for judge in self.judges:
            # Lần 1: Thứ tự bình thường
            result_normal = await judge.judge(question, answer, ground_truth)

            # Lần 2: Đảo vị trí — đặt ground_truth vào chỗ answer
            result_swapped = await judge.judge(question, ground_truth, answer)

            normal_score = result_normal["scores"]["overall"]
            swapped_score = result_swapped["scores"]["overall"]
            score_diff = abs(normal_score - swapped_score)

            bias_results[judge.judge_name] = {
                "normal_score": normal_score,
                "swapped_score": swapped_score,
                "bias_delta": round(score_diff, 2),
                "has_position_bias": score_diff > 1.0,
                "bias_severity": (
                    "high" if score_diff > 1.5
                    else "medium" if score_diff > 0.5
                    else "low"
                )
            }

        return bias_results

    def get_cost_summary(self) -> Dict:
        """Trả về báo cáo tổng hợp chi phí."""
        return self.cost_tracker.summary()


# ============================================================
# Quick Test — Chạy trực tiếp để test
# ============================================================

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    async def test():
        print("=" * 60)
        print("[TEST] Multi-Judge Evaluation Engine")
        print("=" * 60)

        # Sử dụng 2 model của OpenAI để làm Multi-Judge
        judge = LLMJudge(gpt_model_1="gpt-4o-mini", gpt_model_2="gpt-4o")

        if not judge.judges:
            print("[ERROR] Khong tim thay API key. Hay cau hinh .env truoc.")
            return

        print(f"\n[INFO] Judges kha dung: {[j.judge_name for j in judge.judges]}")
        print("\n--- Dang chay evaluate_multi_judge ---")

        result = await judge.evaluate_multi_judge(
            question="Lam the nao de doi mat khau tai khoan?",
            answer="Ban vao Cai dat > Bao mat > Doi mat khau, nhap mat khau cu va mat khau moi.",
            ground_truth="De doi mat khau, vao muc Cai dat, chon Bao mat, nhan Doi mat khau. Nhap mat khau hien tai, nhap mat khau moi 2 lan va nhan Xac nhan."
        )

        print(f"\n[RESULT] Final Score: {result['final_score']}")
        print(f"[RESULT] Agreement Rate: {result['agreement_rate']}")
        print(f"[RESULT] Total Cost: ${result['total_cost_usd']}")

        print("\n[SCORES] Individual Scores:")
        for s in result["individual_scores"]:
            print(f"  [{s['judge_name']}]")
            print(f"    Accuracy: {s['scores']['accuracy']}, Completeness: {s['scores']['completeness']}, Safety: {s['scores']['safety_tone']}")
            print(f"    Overall: {s['scores']['overall']}")
            print(f"    Tokens: {s['token_usage']['total_tokens']}, Cost: ${s['cost_usd']}")
            print(f"    Reasoning: {s['reasoning'][:100]}...")

        print("\n[COST] Cost Summary:")
        print(json.dumps(judge.get_cost_summary(), indent=2, ensure_ascii=False))

    asyncio.run(test())
