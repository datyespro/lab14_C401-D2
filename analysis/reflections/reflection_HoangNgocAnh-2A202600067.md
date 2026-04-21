# Reflection — Member 5: DevOps/Analyst (Regression Gate)

**Họ và tên:** Hoàng Ngọc Anh
**Mã số sinh viên:** 2A202600067

---

## 1. Mục tiêu và Trách nhiệm

Nhiệm vụ của tôi là xây dựng **Regression Gate** — module cuối cùng trong pipeline đánh giá Agent AI. Module này đảm bảo mọi bản cập nhật (V2) chỉ được release khi thực sự cải thiện so với bản đang chạy (V1), đồng thời theo dõi chi phí vận hành để tránh việc tối ưu hóa chất lượng mà phí phạm ngân sách.

---

## 2. Chi tiết Công việc đã thực hiện

### 2.1. Phân tích yêu cầu và thiết kế kiến trúc

Trước khi viết code, tôi đọc toàn bộ codebase (main.py, runner.py, llm_judge.py, retrieval_eval.py, GRADING_RUBRIC.md) để nắm:
- Data flow: Agent → Retrieval → RAGAS → Multi-Judge → Report
- Cấu trúc kết quả benchmark (`reports/benchmark_results.json`)
- Tiêu chí chấm điểm: Regression Testing (10 điểm nhóm) + Technical Depth (15 điểm cá nhân)

Thiết kế class `RegressionGate` gồm 8 method, mỗi method 1 trách nhiệm rõ ràng, dễ debug và mở rộng.

### 2.2. Xây dựng module `engine/regression_gate.py`

#### Threshold và ngưỡng quyết định

Tôi định nghĩa 5 ngưỡng cố định, mỗi ngưỡng đều có cơ sở:

| Ngưỡng | Giá trị | Cơ sở |
|--------|---------|--------|
| `quality_delta_min` | 0.05 | Tránh noise — nếu V2 chỉ cải thiện < 0.05 điểm, có thể do random fluctuation |
| `min_hit_rate` | 0.80 | 80% là ngưỡng tối thiểu cho production RAG system |
| `min_mrr` | 0.60 | Đảm bảo document đúng luôn nằm trong top-k |
| `max_avg_latency_ms` | 3000 | Người dùng chatbot chấp nhận tối đa 3s chờ |
| `max_cost_ratio` | 1.5 | V2 không được đắt gấp 1.5 lần V1 trừ khi có lý do xác đáng |

#### Tính toán Delta và Direction

Dùng `higher_is_better` flag để phân biệt:
- **Higher is better**: avg_score, hit_rate, mrr, faithfulness, relevancy, pass_rate
- **Lower is better**: avg_latency_ms (V2 phải nhanh hơn V1)

Mỗi delta được tính: giá trị tuyệt đối (`v2 - v1`) + phần trăm thay đổi + direction ("improved" / "degraded" / "unchanged").

#### Auto-Gate logic

```
blockers = []
if hit_rate < 0.80: blockers.append("BLOCK")
if mrr < 0.60:      blockers.append("BLOCK")
if score_delta < 0.05: blockers.append("BLOCK")
if latency > 3000ms: blockers.append("BLOCK")
if cost_ratio > 1.5: blockers.append("WARN")  # warning only

decision = "BLOCK" if blockers else "APPROVE"
```

### 2.3. Technical Depth — Giải thích các khái niệm

**MRR (Mean Reciprocal Rank):**
MRR đo thứ hạng của document đúng đầu tiên. Nếu document đúng ở vị trí 1 → MRR = 1.0; ở vị trí 3 → MRR = 0.333. Trong pipeline này, MRR được tính bằng hàm `calculate_mrr` trong `RetrievalEvaluator`, lấy trung bình across all cases.

**Trade-off Chi phí vs Chất lượng:**
Module `_estimate_cost` tính chi phí dựa trên pricing GPT-4o ($0.03/1K input, $0.06/1K output) và Claude-3.5 ($0.003/1K input, $0.015/1K output). Mỗi evaluation gọi 2 model, nên chi phí nhân đôi. Ngưỡng `max_cost_ratio = 1.5` đảm bảo V2 cải thiện chất lượng phải xứng đáng với chi phí tăng thêm.

**Cohen's Kappa (liên quan đến agreement_rate):**
Trong module này, `agreement_rate` giữa 2 judge được tính bằng tỷ lệ scores trùng khớp. Khi 2 model cho kết quả lệch > 1 điểm, hệ thống sẽ cảnh báo xung đột. Đây là cách đơn giản hóa của inter-annotator agreement — trong production có thể dùng Cohen's Kappa để đo độ nhất quán thực sự.

### 2.4. Engineering Contribution — Tối ưu hóa

- **Tái sử dụng code qua `_avg_metric`**: Thay vì viết 8 vòng for riêng biệt, dùng dot-notation path (`"judge.final_score"`) để trích xuất nested dict bất kỳ. Giảm ~40 dòng code và dễ mở rộng khi thêm metric mới.
- **Không động vào file khác**: Chỉ sửa `engine/regression_gate.py`, đảm bảo tương thích ngược với pipeline hiện tại.
- **Export interface rõ ràng**: Hàm `run_regression_gate(v1_results, v2_results)` cho phép `main.py` gọi dễ dàng mà không cần khởi tạo class.

### 2.5. Problem Solving — Vấn đề phát sinh và giải pháp

**Vấn đề 1: File gốc quá dài (800 dòng)**
File `regression_gate.py` ban đầu có ~800 dòng, không đồng nhất với style project (các file khác 30-50 dòng). Tôi phân tích logic chính, loại bỏ boilerplate và code trùng lặp, viết lại còn ~200 dòng mà vẫn giữ đầy đủ chức năng.

**Vấn đề 2: Cấu trúc data không đồng nhất**
Benchmark results có nested dict phức tạp (`ragas.retrieval.hit_rate`, `judge.agreement_rate`). Tôi giải quyết bằng `_avg_metric` với dot-notation parsing, không cần hard-code từng key.

**Vấn đề 3: Threshold không có cơ sở**
Ban đầu đặt ngưỡng arbitrary. Sau đó tôi research và đưa ra cơ sở cho từng con số (hit_rate 80% là standard cho production RAG, latency 3s là UX threshold phổ biến).

### 2.6. Test và xác minh

- Chạy self-test với mock data: 50 cases V1 vs 50 cases V2
- Kết quả: **APPROVE** vì V2 cải thiện +0.40 avg_score, hit_rate 0.90, latency giảm 200ms
- Report lưu tại `reports/regression_report.json`
- Bảng console: V1 | V2 | Delta cho 8 metrics

---

## 3. Kết quả Nhận được

| Kết quả | Trạng thái |
|---------|-----------|
| Module `engine/regression_gate.py` hoạt động đúng | ✅ |
| So sánh V1 vs V2 với Delta Analysis (8 metrics) | ✅ |
| Auto-Gate APPROVE/BLOCK dựa trên 5 ngưỡng | ✅ |
| Báo cáo chi phí USD và token usage | ✅ |
| Report `reports/regression_report.json` đúng format | ✅ |
| Self-test pass — chạy thành công | ✅ |

---

## 4. Bài học Rút ra

1. **Thiết kế nhỏ gọn, có trách nhiệm rõ ràng**: Mỗi method chỉ làm 1 việc, dễ debug và mở rộng khi thêm metric mới.

2. **Threshold cần có cơ sở**: Không đặt ngưỡng arbitrary. Mỗi con số cần research và giải thích được tại sao.

3. **MRR vs Hit Rate phục vụ mục đích khác nhau**: Hit Rate đo "có ít nhất 1 đáp án đúng trong top-k", còn MRR đo "đáp án đúng ở vị trí nào". Cả 2 cùng đánh giá retrieval nhưng nhấn mạnh khác nhau.

4. **Chi phí và chất lượng luôn có trade-off**: Model mạnh hơn (GPT-4o) cho điểm cao hơn nhưng tốn nhiều tiền hơn. Regression Gate giúp cân bằng 2 yếu tố này một cách tự động.

---

## 5. Next Steps (nếu mở rộng)

- Thêm **WARN** decision cho borderline cases — hiện tại chỉ APPROVE/BLOCK, cần ngưỡng trung gian
- Track token thực tế từ LLM response metadata thay vì ước tính cố định
- Thêm visualization (chart V1 vs V2 comparison) vào report JSON
- Hỗ trợ so sánh nhiều phiên bản liên tiếp (V1 → V2 → V3 → ...)

---
