# Reflection — Member 5: DevOps/Analyst (Regression Gate)

**Họ và tên:** Hoàng Ngọc Anh
**Mã số sinh viên:** 2A202600067

---

## 1. Mục tiêu và Trách nhiệm

Nhiệm vụ của tôi là xây dựng **Regression Gate** — module cuối cùng trong pipeline đánh giá Agent AI, đảm bảo rằng mọi bản cập nhật (V2) chỉ được release khi thực sự cải thiện so với bản cũ (V1). Module này chịu trách nhiệm so sánh metrics, đưa ra quyết định tự động (APPROVE / BLOCK), và báo cáo chi phí vận hành.

---

## 2. Chi tiết Công việc đã thực hiện

### 2.1. Phân tích yêu cầu và thiết kế kiến trúc

Trước khi viết code, tôi đã đọc toàn bộ codebase (main.py, runner.py, llm_judge.py, retrieval_eval.py, GRADING_RUBRIC.md) để hiểu rõ:
- Data flow từ Agent → RAGAS → Judge → Report
- Cấu trúc kết quả benchmark (`reports/benchmark_results.json`)
- Yêu cầu chấm điểm: Regression Testing (10 điểm)

Từ đó thiết kế kiến trúc module gồm 1 class chính `RegressionGate` với 8 method, mỗi method phục vụ 1 nhiệm vụ rõ ràng.

### 2.2. Xây dựng module `engine/regression_gate.py`

File `engine/regression_gate.py` (~200 dòng) gồm các thành phần:

- **`__init__`**: Định nghĩa ngưỡng threshold cố định:
  - `quality_delta_min = 0.05` — V2 phải cải thiện score tối thiểu 0.05 điểm so với V1
  - `min_hit_rate = 0.80` — Retrieval phải đạt >= 80%
  - `min_mrr = 0.60` — MRR >= 60%
  - `max_avg_latency_ms = 3000` — Latency trung bình <= 3 giây
  - `max_cost_ratio = 1.5` — Chi phí V2 không vượt quá 1.5 lần V1

- **`_avg_metric`**: Hàm helper tính trung bình metric từ nested dict bằng dot-notation path (ví dụ `"ragas.retrieval.hit_rate"`). Giúp tái sử dụng cho mọi metric mà không cần viết lại logic trích xuất.

- **`_build_summary`**: Tổng hợp 8 metrics từ danh sách results:
  - avg_score, hit_rate, mrr, agreement_rate, avg_latency_ms, faithfulness, relevancy, pass_rate

- **`_estimate_cost`**: Ước tính chi phí USD dựa trên:
  - GPT-4o: $0.03/1K input + $0.06/1K output
  - Claude-3.5: $0.003/1K input + $0.015/1K output
  - Token giả định cố định (150 input + 80 output mỗi model mỗi case)

- **`compare`**: So sánh V1 vs V2:
  - Gọi `_build_summary` cho cả 2 version
  - Tính delta từng metric bằng `_compute_delta` (giá trị tuyệt đối + phần trăm + direction)
  - Tính cost ratio

- **`evaluate_gate`**: Logic Auto-Gate quyết định APPROVE hoặc BLOCK:
  - **BLOCK** nếu bất kỳ ngưỡng nào bị vi phạm: hit_rate, mrr, score_delta, latency
  - **APPROVE** nếu tất cả ngưỡng đều đạt

- **`run`**: Pipeline chính — gọi `compare` → `evaluate_gate` → lưu `reports/regression_report.json` → in bảng console.

### 2.3. Đảm bảo tính nhất quán với project

Module được viết theo đúng style của project:
- File ngắn gọn (tương đương `llm_judge.py` 36 dòng, `runner.py` 49 dòng)
- Không sửa bất kỳ file nào khác (chỉ động vào `engine/regression_gate.py`)
- Export hàm tiện ích `run_regression_gate()` để `main.py` có thể gọi dễ dàng

### 2.4. Test và xác minh

- Chạy self-test với mock data (50 cases V1 vs 50 cases V2)
- Xác nhận gate decision đúng: V2 cải thiện → **APPROVE**
- Report JSON lưu đúng tại `reports/regression_report.json`
- Bảng so sánh in ra console với đầy đủ delta metrics

---

## 3. Kết quả Nhận được

| Kết quả | Trạng thái |
|---------|-----------|
| Module `engine/regression_gate.py` hoạt động | ✅ |
| Delta Analysis cho 8 metrics | ✅ |
| Auto-Gate (APPROVE/BLOCK) | ✅ |
| Báo cáo chi phí USD/token | ✅ |
| Report `reports/regression_report.json` | ✅ |
| Self-test pass | ✅ |

---

## 4. Bài học Rút ra

1. **Thiết kế module nhỏ, có trách nhiệm rõ ràng**: Mỗi method chỉ làm 1 việc, dễ debug và mở rộng.

2. **Threshold cần dựa trên business context**: Ngưỡng 0.05 cho quality_delta và 0.80 cho hit_rate là con số hợp lý cho hệ thống QA chatbot, nhưng cần review lại theo từng use-case cụ thể.

3. **Chi phí ước tính vs thực tế**: Module hiện dùng token cố định giả định. Trong production, cần track token thực tế từ LLM response metadata để báo cáo chính xác hơn.

4. **Regression Gate là lớp phòng thủ cuối cùng**: Nhiều team bỏ qua bước này, dẫn đến release bản kém hơn bản đang chạy. Có auto-gate giúp giảm rủi ro đáng kể.

---

## 5. Next Steps (nếu mở rộng)

- Thêm **WARN** decision — hiện tại chỉ có APPROVE/BLOCK, có thể thêm ngưỡng borderline
- Tích hợp track token thực tế từ LLM responses thay vì ước tính
- Thêm visualization (bảng so sánh V1/V2 chart) vào report JSON
- Hỗ trợ so sánh nhiều phiên bản (V1 vs V2 vs V3)

---
