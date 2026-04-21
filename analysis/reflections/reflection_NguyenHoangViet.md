# Reflection — Data Lead - Dataset & SDG (Member 1 - Nguyễn Hoàng Việt)

Tôi phụ trách phần xây dựng Golden Dataset và script SDG, tập trung vào file `data/synthetic_gen.py`.

Những việc đã làm:
- Thiết kế lại `synthetic_gen.py` để sinh dữ liệu dựa trên toàn bộ tài liệu trong `data/documents/` thay vì tạo thủ công từng case.
- Tích hợp `gemini-2.5-flash` để sinh cặp Q/A, đọc cấu trúc JSON từ model và chuẩn hóa lại trước khi ghi ra `data/golden_set.jsonl`.
- Tham khảo `HARD_CASES_GUIDE.md` để đảm bảo dataset có đủ các nhóm case quan trọng như factual, policy-detail, FAQ, adversarial prompt injection, conflict-check và out-of-context.
- Thêm cơ chế sinh theo từng document để tránh vượt giới hạn token, đồng thời có dedup theo question để giảm trùng lặp.
- Xây dựng fallback dataset để pipeline vẫn chạy được khi thiếu API key, thiếu thư viện `google-genai`, hoặc không có dữ liệu nguồn.

Kết quả đạt được:
- File `synthetic_gen.py` có thể tạo Golden Dataset ổn định và phù hợp với corpus nội bộ.
- Dataset đầu ra có schema nhất quán, gồm `question`, `expected_answer`, `context`, `expected_retrieval_ids` và `metadata`.
- Script có thể tự đảm bảo số lượng case tối thiểu theo yêu cầu bài lab, đồng thời vẫn giữ được các hard cases cần thiết cho benchmark.

Bài học & next steps:
- Khi sinh dữ liệu benchmark, cần ưu tiên tính nhất quán của schema và khả năng chạy lại nhiều lần hơn là chỉ tăng số lượng case.
- Nếu có thêm thời gian, tôi muốn mở rộng prompt để sinh thêm multi-document questions và kiểm soát chất lượng đầu ra chặt hơn theo từng document.

Thời gian hoàn thành: 2026-04-21

