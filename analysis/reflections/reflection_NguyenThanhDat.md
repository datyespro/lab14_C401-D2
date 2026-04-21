# 📑 Individual Report: Báo cáo công việc cá nhân

Họ và tên: Nguyễn Thành Đạt  
Mã số học viên: 2A202600203  
Vai trò trong Lab: (Phụ trách Multi-Judge Engine)  

---

## I. MỤC TIÊU VÀ ĐÓNG GÓP (Engineering Contribution)
Nhiệm vụ cốt lõi của tôi trong Lab 14 là thiết kế và khởi tạo trái tim của hệ thống đánh giá tự động "Multi-Judge Benchmark Engine". Tôi đảm nhiệm từ khâu khởi chạy mô hình song song (Người 3) đến chiến lược đồng thuận - xử lý xung đột của hội đồng Giám khảo (Người 4). Cụ thể như sau:

---

## II. ĐÁP ỨNG CÁC TIÊU CHÍ NHÓM (Group Metrics)

### 1. Multi-Judge Consensus Engine 
- **Triển khai Multi-Model:** Thay vì dùng single judge, tôi đã xây dựng Class `GPTJudge` linh hoạt và chạy song song 2 phiên bản AI với tính cách khác nhau: `gpt-4o-mini` (evaluate nhanh/rẻ) và `gpt-4o` (evaluate khắt khe/sâu sắc) làm song giám khảo.
- **Rubrics chi tiết:** Thiết kế hệ thống System Prompt trả về JSON đánh giá chính xác chuẩn xác cho 3 tiêu chí cốt lõi định tính thành định lượng: `Accuracy` (Độ chính xác), `Completeness` (Độ đầy đủ), và `Safety/Tone` (Tính an toàn).
- **Thuật toán Đồng thuận tự động (Consensus Logic):** Xây dựng bộ phân giải điểm dựa theo logic:
  - Lệch ≤ 0.5: Đồng thuận tuyệt đối (100% Agreement).
  - Lệch ≤ 1.0: Đồng thuận tương đối (70% Agreement).
  - **Conflict Resolution mechanism:** Nếu 2 giám khảo cãi nhau (Lệch > 1.0 điểm), hệ thống đánh Agreement Rate = 0% và kích hoạt chế độ Cảnh báo Cực đoan (**Strict Calibration**). Model sẽ ghi đè điểm bằng `Min(score1, score2)` để quản lý yếu tố rủi ro, và nối hai luồng suy luận vào 1 flag lớn: `[⚠️ CẢNH BÁO XUNG ĐỘT]` lưu trữ thẳng ra log để chuyên gia con người dễ dàng xem xét lại thay vì để trôi lỗi (false positive).

### 2. Tối ưu Code & Đo lường (Performance & Cost )
- **Asynchronous Pipeline chạy siêu tốc:** Ứng dụng `asyncio.gather` để mở đa luồng gọi requests song song cho tất cả các cases thay vì duyệt `for` tuần tự. Nhờ kiến trúc bất đồng bộ này, việc đánh giá cả dataset 50+ câu hỏi bởi nhiều Model hoàn thành cực nhanh (thỏa mãn tiêu chí < 2 phút theo yêu cầu bài toán).
- **Quản lý Token MLOps:** Tự động bắt tín hiệu Metadata từ HTTP responses để ghi nhận `prompt_tokens`, `completion_tokens`. Xây dựng module `CostTracker` tự động mapping với Pricing ($) chuẩn của API để sinh bảng biến động chi phí (`cost_per_eval`) tại từng thời điểm.

---

## III. CHIỀU SÂU KỸ THUẬT VÀ PROBLEM SOLVING (Điểm Cá Nhân)

### 1. Problem Solving 
Trong tuần chạy dự án, tôi đã giải quyết những technical blockers quan trọng cứu dự án khỏi rủi ro quá hạn:
- **Xử lý sự cố "429 Rate Limit" & Self-Healing:** Khi tài khoản Google Gemini mặc định trong dự án bị cạn tín dụng (Credit Depleted) làm đánh sập các function GenData và Eval. Tôi ngay lập tức thiết kế kiến trúc "Graceful Degradation": refactor pipeline để móc nối fallback sang 2 Model cực mạnh khác của hệ sinh thái OpenAI thay thế, giúp Pipeline tự động phục hồi luồng hoạt động chạy trơn tru đến phút cuối. Thêm logic "Single Judge Fallback" để nếu 1 judge bất ngờ sập, benchmark vẫn ra kết quả thay vì error crash toàn cục.
- **Kỷ luật Mã nguồn (Git Hygiene):** Kịp thời phát hiện lệnh `git add` nhầm 15.000 file rác của môi trường ảo (lỗi không map `/venv` trong `.gitignore`). Tôi đã Un-stage và cấu hình lại rules git ignore chuẩn để giữ size repository chung của cả nhóm sạch đẹp và nhỏ gọn.

### 2. Technical Depth 
Đã ứng dụng được các định nghĩa cốt lõi của LLMOps / MLOps:
- **Cohen's Kappa & Agreement Metrics:** Chỉ số `Agreement Rate` do tôi phân tích đã được áp dụng bản chất mô phỏng độ Kappa để lượng hóa xem mức độ đồng nhất (Inter-rater reliability) giữa 2 con AI Judge.
- **Cost vs Quality Trade-off:** Tracking cost chỉ ra rằng dùng model To (`gpt-4o`) tiêu thụ ngân quỹ đắt đỏ hơn nhiều lần model Nhỏ (`gpt-4o-mini`). Giải pháp đưa ra là `gpt-4o-mini` đủ tốt cho các task xác minh thông tin tuyến tính, nên về dài hạn chúng ta có thể áp dụng `gpt-4o` ở quy mô hẹp hơn – ví dụ như làm Meta-Judge chỉ chuyên đi can thiệp xử lý Conflict – tiết kiệm chi phí tối đa cho doanh nghiệp.
- **Position Bias (Phòng vệ Thiên vị vị trí):** Đã phân chia tiêu chí đánh giá thành các dimensions siêu nhỏ thay vì prompt AI tổng hợp điểm 1 lượt, ngăn ngừa việc AI thiên vị luồng thông tin vào sau (recency bias) hoặc vào trước (primacy bias) khi review kết quả của Agent.

🚀 *Kết luận: Đã hoàn thiện xuất sắc module Judge. File check `check_lab.py` trả về dòng trạng thái xanh: `Multi-Judge Metrics: Available` (Hit Rate và Agreement Rate 100% khớp file summary).*
