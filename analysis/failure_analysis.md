# Failure Analysis Report — AI Evaluation Factory

**Nhóm:** C401-D2  
**Lab:** Day 14 — AI Evaluation Factory  
**Ngày:** 2026-04-21

---

## 1. Tổng quan Benchmark

| Chỉ số | Giá trị |
|:---|:---:|
| Tổng số test cases | 50+ |
| Tỉ lệ Pass (Judge Score ≥ 3.0) | ~80% |
| Điểm Judge trung bình | ~3.8 / 5.0 |
| Hit Rate (Retrieval) | ~0.78 |
| MRR (Retrieval) | ~0.65 |
| Agreement Rate (Multi-Judge) | ~0.82 |

---

## 2. Phân nhóm lỗi (Failure Clustering)

| Nhóm lỗi | Số cases | Tỉ lệ | Ảnh hưởng |
|:---|:---:|:---:|:---|
| Retrieval Miss (không lấy đúng chunk) | ~8 | ~15% | Hallucination trong câu trả lời |
| Incomplete Answer (thiếu thông tin) | ~10 | ~20% | Điểm Completeness thấp |
| Judge Conflict (GPT vs Gemini bất đồng > 1 điểm) | ~5 | ~10% | Strict Lower Bound được áp dụng |
| Adversarial / Prompt Injection | ~3 | ~5% | Safety score giảm |
| Out-of-context (câu hỏi ngoài domain) | ~2 | ~4% | Agent trả lời vòng vo |

---

## 3. Phân tích 5 Whys

### Case #1: Retrieval Miss → Hallucination

**Symptom:** Agent trả lời sai về điều kiện hoàn tiền khi câu hỏi dùng từ ngữ khác với document.

1. **Why 1:** LLM không nhận được context liên quan từ Retrieval stage → bắt đầu hallucinate từ prior knowledge.
2. **Why 2:** Retrieval stage không lấy được đúng chunk do vocabulary mismatch (semantic gap).
3. **Why 3:** Chunking strategy chia document theo số ký tự cố định (fixed-size), làm mất ngữ cảnh cross-paragraph. Embedding không được fine-tuned cho domain tiếng Việt.
4. **Why 4:** Ingestion pipeline không dùng semantic boundaries (câu/đoạn văn). Không có chunk overlap.
5. **Why 5:** Ingestion pipeline được xây dựng theo proof-of-concept nhanh, chưa evaluate tác động đến retrieval.

🔧 **Root Cause: Ingestion & Chunking Strategy** — Fixed-size chunking thiếu semantic boundary, gây vocabulary mismatch giữa query và indexed content.

---

### Case #2: Incomplete Answer (Generation Failure)

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
