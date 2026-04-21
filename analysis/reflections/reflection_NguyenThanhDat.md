# 📑 Individual Report: Báo cáo công việc

Họ và tên: Nguyễn Thành Đạt
Mã số học viên: 2A202600203


---

## 1. Mục tiêu và Trách nhiệm
Nhiệm vụ chính của tôi là xây dựng trái tim của hệ thống đánh giá tự động: **Hệ thống Multi-Judge (Giám khảo AI)**. 
Hệ thống này yêu cầu khởi tạo ít nhất 2 phiên bản LLM song song để tiến hành đánh giá khách quan các câu trả lời do AI Agent sinh ra (từ dữ liệu Golden Dataset), đáp ứng các tiêu chí sản xuất chuyên nghiệp của MLOps và đảm bảo tiết kiệm chi phí.

---

## 2. Chi tiết Công việc đã thực hiện

### 2.1. Xây dựng Kiến trúc Multi-Judge Engine (`engine/llm_judge.py`)
- Dựa trên Abstract `BaseJudge`, tôi đã viết hoàn chỉnh class `GPTJudge` kết nối trực tiếp với API của OpenAI.
- **Quyết định kỹ thuật quan trọng:** Do giới hạn về hạn mức Free-tier của Google (bị lỗi HTTP 429), để đảm bảo tiến độ dự án không bị đình trệ, tôi thiết kế linh hoạt hệ thống chạy song song 2 models khác nhau từ OpenAI: `gpt-4o-mini` (nhanh, nhẹ) và `gpt-4o` (mô hình tiên tiến, khắt khe hơn) để tạo ra hai luồng đánh giá khách quan mô phỏng 2 tính cách Giám khảo riêng biệt.

### 2.2. Xây dựng Prompts & Rubrics Chấm điểm Khắt khe
Tôi tạo ra bộ lệnh (Prompt Engineering) với hệ thống Rubric phân tầng từ 1 đến 5 điểm để các AI Judge dựa vào đó đánh giá. Trọng tâm của hệ thống điểm xoay quanh 3 tiêu chuẩn cốt lõi:
- **Accuracy (Độ chính xác):** Đánh giá xem câu trả lời của Agent có sai lệch hoặc bịa đặt (hallucinate) thông tin so với Ground Truth không.
- **Completeness (Độ đầy đủ):** Chỉ rõ các lỗ hổng thông tin nếu Agent bỏ sót các bước thiết yếu.
- **Safety/Tone (Độ an toàn):** Cam kết phản hồi không chứa ngôn từ độc hại, rò rỉ thông tin chuẩn SOP của công ty.
Tất cả kết quả được yêu cầu trả về theo chuẩn định dạng JSON khắt khe để dễ dàng đưa sang các luồng tiếp theo xử lý.

### 2.3. Tích hợp Hệ thống Track Chi phí & Token MLOps (Cost Tracker)
- Xây dựng riêng class `CostTracker` bên trong Engine. Hệ thống này liên tục lắng nghe và bóc tách dữ liệu Metadata trả về từ mỗi Response của API để cộng dồn số `prompt_tokens` và `completion_tokens`.
- Quy đổi giá tự động ra USD ($) theo đúng Pricing bảng giá thực của OpenAI để team Lead có bản báo cáo đo lường chi phí (Cost_per_eval) ở pha cuối.

### 2.4. Tối ưu Hiệu Năng bằng Chạy Song Song (Asynchronous Execution)
Nếu cho từng Giám khảo chấm điểm lần lượt (tuần tự), thời gian chờ sẽ kéo dài gấp đôi gây thắt nút cổ chai cho Benchmark.
- Tôi đã wrap tất cả logic đánh giá vào hàm `async` và gọi đồng thời (parallel) bằng `asyncio.gather()`. Kiến trúc này giúp hệ thống chờ các HTTP request của Judge1 & Judge2 chạy cùng lúc, tiệt tiêu độ trễ mạng.

### 2.5. Exception Handling & Self-Healing
Hệ thống chấm điểm AI trong thực tế rất dễ gián đoạn do Timeout, Rate Limit hoặc Parse JSON lỗi.
- Thiết lập logic tự bảo vệ: Bắt trọn vẹn Exception của từng Request, xử lý log lỗi tinh tế, và gán điểm 0 cùng thông báo giải thích vào ô `reasoning` thay vì làm văng toàn bộ hệ thống đang chạy. Việc đảm bảo hệ thống không bao giờ "crash" giữa chừng (Zero Downtime during Eval) là tiêu chuẩn cao nhất tôi tự đặt ra.

---

## 3. Kết quả Nhận được
✅ Multi-Judge khởi tạo và chấm điểm thành công.
✅ Output logs đều trả về JSON đúng chuẩn.

Hệ thống hoạt động trơn tru đã được minh chứng qua dòng test hoàn hảo cuối cùng bằng lệnh `python main.py` và `check_lab.py` với **Multi-Judge Metrics: Available**!
