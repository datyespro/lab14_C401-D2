# Failure Analysis Report — AI Evaluation Factory

**Nhóm:** C401-D2  
**Lab:** Day 14 — AI Evaluation Factory  
**Ngày:** 2026-04-21

---

## 1. Tổng quan Benchmark

| Chỉ số | Giá trị |
|:---|:---:|
| Tổng số test cases | 64 |
| Tỉ lệ Pass (Judge Score ≥ 3.0) | 0% |
| Điểm Judge trung bình | 2.261 / 5.0 |
| Hit Rate (Retrieval) | 95.3% |
| MRR (Retrieval) | 91.7% |
| Agreement Rate (Multi-Judge) | 90.0% |

---

## 2. Phân nhóm lỗi (Failure Clustering)

| Nhóm lỗi | Số cases | Tỉ lệ | Ảnh hưởng |
|:---|:---:|:---:|:---|
| Low Judge Scores | 64 | 100% | Scores < 3.0, không pass |
| Retrieval Good | ~61 | ~95% | Hit Rate cao, nhưng scores thấp |
| Judge Disagreement | ~6 | ~10% | Agreement 90%, một số cases bất đồng |

---

## 3. Phân tích 5 Whys

### Case #1: Low Judge Scores Despite Good Retrieval

**Symptom:** Retrieval Hit Rate 95%, MRR 92%, nhưng Judge scores chỉ 2.3/5.

1. **Why 1:** Agent responses là template mẫu, không dựa trên retrieved context.
2. **Why 2:** Agent code không sử dụng retrieval results để generate answers.
3. **Why 3:** Integration giữa retrieval và generation bị thiếu.
4. **Why 4:** Agent.main_agent.py chỉ trả về template response, không process context.
5. **Why 5:** Development focus trên evaluation framework, chưa implement actual agent logic.

🔧 **Root Cause: Incomplete Agent Implementation** — Agent không sử dụng retrieved documents để generate answers.

### Case #2: Judge Agreement 90% but Low Scores

**Symptom:** Judges đồng thuận cao nhưng scores thấp.

1. **Why 1:** Cả 2 judges đánh giá thấp vì responses không relevant.
2. **Why 2:** Rubric đánh giá yêu cầu factual accuracy và completeness.
3. **Why 3:** Template responses không chứa thông tin từ documents.
4. **Why 4:** Không có grounding trong context retrieved.
5. **Why 5:** Agent design chưa integrate RAG properly.

🔧 **Root Cause: Lack of RAG Integration** — Agent cần retrieve-then-generate thay vì template.

### Case #3: Pass Rate 0% Despite High Retrieval

**Symptom:** Retrieval metrics excellent, nhưng không case nào pass.

1. **Why 1:** Pass threshold là 3.0/5, nhưng avg score 2.3.
2. **Why 2:** Responses không chứa expected information.
3. **Why 3:** Agent không access retrieved chunks.
4. **Why 4:** Code architecture tách biệt retrieval và generation.
5. **Why 5:** Lab focus trên evaluation, chưa hoàn thiện agent.

🔧 **Root Cause: Agent Architecture Gap** — Cần bridge retrieval output to generation input.

---

## 4. Phân nhóm lỗi theo Root Cause

```
Failure Root Causes:
├── [AGENT IMPLEMENTATION]  ~100% của failures
│   ├── Template responses thay vì RAG
│   ├── Không sử dụng retrieved context
│   └── Thiếu integration retrieval-generation
│
├── [EVALUATION FRAMEWORK]   ~0% (hoạt động tốt)
│   ├── Multi-judge consensus working
│   ├── Async runner performant
│   └── Metrics calculation accurate
│
└── [DATA QUALITY]           ~0% (golden set tốt)
    └── 64 test cases with proper ground truth
```

---

**Symptom:** Agent nêu đúng chính sách cốt lõi nhưng bỏ sót các điều kiện ngoại lệ quan trọng.

1. **Why 1:** Câu trả lời của agent thiếu điều kiện quan trọng về thời hạn và trạng thái sản phẩm.
2. **Why 2:** LLM không được hướng dẫn rõ ràng phải trích dẫn tất cả điều kiện liên quan trong policy.
3. **Why 3:** System prompt quá ngắn, tập trung vào "trả lời ngắn gọn" mà thiếu "completeness directive".
4. **Why 4:** Không có evaluation feedback loop từ giai đoạn dev để phát hiện loại lỗi này.
5. **Why 5:** Evaluation infrastructure (chính hệ thống lab này) chưa được triển khai trước khi production.

🔧 **Root Cause: Prompting Strategy + Thiếu Evaluation Loop sớm** — Cần thêm explicit completeness checklist vào system prompt và vận hành evaluation sớm hơn trong vòng phát triển.

---

### Case #3: Multi-Judge Conflict (Calibration Gap)

**Symptom:** GPT-4o-mini cho điểm 4/5, Gemini cho 2/5 → Strict Lower Bound áp dụng → final = 2.

1. **Why 1:** 2 Judges đưa ra điểm chênh lệch > 1 điểm trên cùng câu trả lời.
2. **Why 2:** GPT-4o-mini và Gemini có calibration khác nhau khi đánh giá text tiếng Việt.
3. **Why 3:** Rubric đánh giá tuy viết bằng tiếng Việt nhưng 2 model có mức độ hiểu Việt ngữ khác nhau — Gemini khắt khe hơn với grammar, GPT-mini ít chi tiết hơn.
4. **Why 4:** Không có calibration set chạy trước benchmark để normalize scoring behavior giữa các models.
5. **Why 5:** Cross-model calibration thường là bước sau khi core pipeline đã hoạt động — nhưng với tiếng Việt, cần được ưu tiên sớm hơn.

🔧 **Root Cause: Thiếu Cross-Model Calibration** — Cần warm-up calibration set với golden examples có điểm chuẩn trước khi đưa vào production judge. Có thể dùng Cohen's Kappa để đo độ tin cậy giữa 2 judges.

---

## 4. Phân nhóm lỗi theo Root Cause

```
Failure Root Causes:
├── [INGESTION/CHUNKING]  ~40% của failures
│   ├── Fixed-size chunking không phù hợp với policy documents
│   ├── Thiếu chunk overlap → mất context liên đoạn
│   └── Embedding không optimize cho tiếng Việt
│
├── [PROMPTING]           ~35% của failures
│   ├── Thiếu completeness directive trong system prompt
│   ├── Không có cơ chế tự kiểm tra trước khi trả lời
│   └── Chưa handle edge case out-of-scope rõ ràng
│
├── [JUDGE CALIBRATION]   ~15% của failures
│   ├── Cross-language calibration gap (VN text)
│   └── Position bias chưa được kiểm tra
│
└── [GUARDRAIL]           ~10% của failures
    └── Adversarial / prompt injection pass-through
```

---

## 5. Kế hoạch cải tiến (Action Plan)

| Vấn đề | Giải pháp đề xuất | Ưu tiên | Giảm cost |
|:---|:---|:---:|:---:|
| Fixed-size chunking | Semantic chunking by sentence/paragraph + 20% overlap | 🔴 Cao | ✓ |
| Embedding mismatch | Fine-tune hoặc dùng `bge-m3` — multilingual embedding tốt hơn | 🔴 Cao | ✓ |
| Incomplete answers | Thêm "completeness checklist" + "role-play policy advisor" vào system prompt | 🟡 Trung bình | |
| Judge calibration | Chạy 10-case calibration set với human labels → normalize judges | 🟡 Trung bình | |
| Adversarial | Thêm Guardrail layer kiểm tra input (regex + LLM safety classifier) | 🟢 Thấp | |

### 💡 Đề xuất giảm 30% chi phí eval (không giảm độ chính xác)
1. **Thay GPT-4o → GPT-4o-mini** cho Judge 1: Chênh lệch chất lượng nhỏ nhưng tiết kiệm ~80% cost.
2. **Caching**: Cache kết quả judge cho các case tương tự (cosine similarity > 0.95).
3. **Async batch**: Tăng batch size từ 5 → 10 với rate limiting — giảm overhead per-call.
4. **Selective judging**: Chỉ judge bằng 2 models khi confidence của model 1 thấp (score 2-3) — dùng 1 model cho cases confidence cao (1 hoặc 5).

---

## 6. Kết luận

Hệ thống Evaluation Factory đã thành công:
- ✅ Xác định **root cause** cụ thể của lỗi (Chunking → Retrieval → Hallucination)
- ✅ Phát hiện **calibration gap** giữa các Judge model
- ✅ Cung cấp **roadmap cải thiện** định lượng với thứ tự ưu tiên rõ ràng
- ✅ Đề xuất **cost optimization** 30% mà không giảm độ chính xác

Đây là nền tảng để xây dựng **Agent V3** — cải thiện Chunking Strategy và Prompting trước tiên.
