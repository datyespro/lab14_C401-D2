# Cá nhân: Báo cáo & Phản ngẫm (Reflection)

**Họ và tên:** Nguyễn Anh Đức  
**Vai trò ban đầu:** Thành viên 4 (Multi-Judge Consensus Engine - Conflict logic)  
**Vai trò thực tế đã đảm nhận:** Integration Lead / QA Engineer  

---

## 1. Công việc ban đầu được phân công
Theo kế hoạch của nhóm, tôi đảm nhận vai trò **Member 4**, phụ trách xử lý Conflict Resolution (giải quyết xung đột) cho Multi-Judge Engine. Nhiệm vụ chính là đảm bảo khi GPT-4o và Gemini có sự chênh lệch điểm số, hệ thống sẽ tự động đối chiếu điểm và áp dụng thuật toán tìm ra mức đồng thuận an toàn nhất (ví dụ áp dụng chiến lược Strict Lower Bound).

Tuy nhiên, do khối lượng công việc ở phần này khá nhỏ và đã được hoàn thành nhanh chóng nhờ phối hợp tốt với Member 3, tôi nhận thấy một "nút thắt cổ chai" lớn của cả hệ thống lúc đó: **Sự rời rạc giữa các module.** 

Mọi người (Data, Retrieval, Judge, Gate) đều hoàn thành xuất sắc package của mình, nhưng file `main.py` và `runner.py` ở trung tâm lại chỉ đang gọi các Mock Class giả lập, dẫn đến việc Pipeline chưa bao giờ được chạy thử thực tế ngoài đời.

---

## 2. Phần nâng cấp và Tích hợp toàn diện (Upgrade Codebase)
Để giải quyết sự rời rạc, tôi đã chủ động thay đổi vai trò sang Integration Lead và tiến hành một cuộc đại tu (upgrade) lớn trên toàn bộ codebase, kết nối tất cả những mảnh ghép thành một **Evaluation Factory khép kín**:

**A. Tích hợp Pipeline (`main.py` & `runner.py`)**
- Xóa bỏ toàn bộ các Mock Class vô nghĩa trong `main.py`.
- Khởi tạo và luân chuyển Data Dict chuẩn hóa từ `MainAgent` → qua `RetrievalEvaluator` (chấm RAGAS) → qua `LLMJudge` (chấm Consensus) → cuối cùng đưa vào so sánh phiên bản trong `RegressionGate`.
- Thêm `asyncio.Semaphore` trong `runner.py` để giới hạn số lượng request gọi song song (Concurrency control), đồng thời bọc `return_exceptions=True` để đảm bảo 1 testcase lỗi (như đứt mạng API) sẽ không làm gãy toàn bộ quá trình Benchmark.

**B. Hoàn thiện Retrieval Engine (`engine/retrieval_eval.py`)**
- Cấu hình lại VectorDB "hoạt động thật" cho scope bài Lab.
- Thay thế danh sách trả về Hardcode `["dummy_doc"]` bằng việc viết class `LightweightKeywordDB` (áp dụng TF-IDF weighting cơ bản). Nó sẽ chủ động đọc toàn bộ kho `.txt` trong `data/documents/` và query ra các `retrieved_ids` dựa trên semantic keywords. Việc này giúp cho metric Hit Rate và MRR cuối cùng mang ý nghĩa đo lường chất lượng thực tiễn thay vì điểm ảo.

**C. Sửa lỗi & Tối ưu Data Generation (`data/synthetic_gen.py`)**
- Script cũ gặp lỗi khi phải ép LLM sinh 50+ cases một lúc (vượt quá token window hoặc trả về JSON lỗi do bị ngắt giữa chừng).
- Tôi đã viết lại luồng xử lý: Chia nhỏ batch theo từng Document. Mỗi Document sẽ call API song song một lần để sinh ra tập subset, sau đó tổng hợp lại và áp dụng cơ chế Deduplication dựa trên câu hỏi để tránh các câu trùng lặp, đảm bảo luôn đáp ứng con số tối thiểu `TARGET_CASES = 50`.

---

## 3. Bài học rút ra (Learnings)
- **Hệ thống hóa đánh giá là một bài toán khó:** Khi xây một Agent, chúng ta chỉ cần lo lắng về một luồng input/output. Nhưng khi xây dựng một *Evaluation Pipeline*, ta phải quản lý rate limit cho hàng trăm vòng lặp LLM calling song song, quản lý JSON parser chặt chẽ vì Output của Model đôi khi không đúng schema như kỳ vọng.
- **Micro-services in Python:** Việc các thành viên code theo các Engine độc lập nhau đã thể hiện rõ điểm lợi hại của Object Oriented Programming và loose-coupling. Nhờ các bạn định nghĩa Interface chuẩn đầu vào/ra, việc tôi làm khâu "dây nối" ở giữa đã diễn ra mượt mà hơn.
- **Sự cần thiết của Async:** Với 64 cases và 2 model Judge gọi song song, nếu lập trình đồng bộ (Synchronous) thông thường, Benchmark sẽ mất khoảng hơn 10 - 15 phút. Nhờ `asyncio`, chi phí thời gian được co lại thành ~60 giây. Cực kỳ ấn tượng!

---

## 4. Giải trình kỹ thuật về Trade-off (Cost vs Quality)
Trong quá trình upgrade Judge Engine, tôi phải quyết định gọi mô hình nào. Việc gọi 2 Judge `gpt-4o` song song sẽ mang lại sự chắc chắn tuyệt đối nhưng làm Cost tăng vọt. 
Quyết định cuối cùng (như thể hiện ở `main.py`): Sử dụng `gpt-4o-mini` làm Baseline Judge và `gpt-4o` làm Premium Judge. Điều này giảm chi phí xuống khoảng **80%** nhưng vẫn giữ được cơ chế bắt ảo giác xuất sắc của GPT-4o những khi GPT-4o-mini bị nhầm lẫn. "Strict Lower Bound" ở conflict logic đã đóng vai trò chốt chặn an toàn cuối cùng để bảo đảm chất lượng.
