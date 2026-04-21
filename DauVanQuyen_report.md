# 🚀 Hướng Dẫn Nhiệm Vụ Bài Lab Day 14: AI Evaluation Factory (Team Edition)

## 🎯 Mục Tiêu Chính Của Bài Lab

Bài lab này yêu cầu nhóm bạn xây dựng một **hệ thống đánh giá tự động chuyên nghiệp** để kiểm tra và đo lường hiệu suất của AI Agent. Thay vì chỉ nói "Agent này tốt" hay "Agent này tệ", hệ thống của bạn phải cung cấp bằng chứng cụ thể bằng con số: Agent mạnh ở đâu, yếu ở đâu, và tại sao.

Hệ thống này giống như một "nhà máy kiểm tra chất lượng" cho AI, giúp đảm bảo rằng Agent hoạt động đáng tin cậy trước khi được triển khai thực tế.

---

## 🕒 Lịch Trình Thực Hiện (4 Tiếng)

Bài lab được chia thành 4 giai đoạn chính, mỗi giai đoạn có mục tiêu rõ ràng:

### Giai Đoạn 1 (45 phút): Chuẩn Bị Dữ Liệu Đánh Giá
- **Thiết kế Golden Dataset**: Tạo ra một bộ dữ liệu chuẩn (ít nhất 50 câu hỏi/test case) để dùng làm tiêu chuẩn đánh giá.
- **Script SDG (Synthetic Data Generation)**: Viết mã để tự động tạo ra các câu hỏi và câu trả lời đúng (ground truth) từ tài liệu có sẵn.
- **Mục tiêu**: Có đủ dữ liệu chất lượng để kiểm tra Agent một cách công bằng.

### Giai Đoạn 2 (90 phút): Xây Dựng Công Cụ Đánh Giá
- **Eval Engine**: Phát triển hệ thống đánh giá sử dụng các công cụ như RAGAS (đánh giá Retrieval-Augmented Generation) và Custom Judge (AI làm giám khảo).
- **Async Runner**: Tạo hệ thống chạy đánh giá bất đồng bộ (không chờ đợi từng bước) để tăng tốc độ.
- **Mục tiêu**: Hệ thống có thể tự động đánh giá Agent nhanh chóng và chính xác.

### Giai Đoạn 3 (60 phút): Chạy Đánh Giá Và Phân Tích
- **Chạy Benchmark**: Thực hiện đánh giá trên toàn bộ bộ dữ liệu chuẩn.
- **Phân Cụm Lỗi (Failure Clustering)**: Nhóm các lỗi tương tự lại với nhau để dễ phân tích.
- **Phân Tích "5 Whys"**: Tìm nguyên nhân gốc rễ của lỗi bằng cách hỏi "Tại sao?" liên tiếp 5 lần.
- **Mục tiêu**: Biết chính xác Agent gặp vấn đề ở đâu và lý do tại sao.

### Giai Đoạn 4 (45 phút): Cải Thiện Và Báo Cáo
- **Tối Ưu Agent**: Dựa trên kết quả đánh giá, sửa đổi Agent để hoạt động tốt hơn.
- **Hoàn Thiện Báo Cáo**: Viết báo cáo chi tiết về quá trình và kết quả.
- **Mục tiêu**: Agent được cải thiện và có tài liệu đầy đủ để nộp bài.

---

## 🛠️ Nhiệm Vụ Chi Tiết Cho Từng Nhóm

Bài lab được thiết kế theo mô hình nhóm, mỗi nhóm chuyên trách một phần:

### 1. Nhóm Data (Retrieval & SDG)
- **Đánh giá Retrieval**: Tính toán tỷ lệ chính xác (Hit Rate) và thứ hạng trung bình (MRR) cho cơ sở dữ liệu vector. Bạn phải chứng minh rằng bước tìm kiếm tài liệu hoạt động tốt trước khi đánh giá phần tạo câu trả lời.
- **Tạo SDG**: Phát triển script để tạo ít nhất 50 test case chất lượng, bao gồm cả ID của tài liệu đúng (ground truth) để đo lường độ chính xác.
- **Tại Sao Quan Trọng**: Nếu retrieval không tốt, Agent sẽ trả lời sai ngay từ đầu, nên việc đánh giá này giúp phát hiện sớm vấn đề.

### 2. Nhóm AI/Backend (Multi-Judge Consensus Engine)
- **Consensus Logic**: Sử dụng ít nhất 2 mô hình AI khác nhau làm "giám khảo" để đánh giá câu trả lời của Agent.
- **Calibration**: Tính toán tỷ lệ đồng thuận giữa các giám khảo và tự động xử lý khi chúng cho điểm khác nhau.
- **Tại Sao Quan Trọng**: Một giám khảo duy nhất có thể thiên vị; việc dùng nhiều giám khảo giúp đảm bảo đánh giá khách quan và đáng tin cậy.

### 3. Nhóm DevOps/Analyst (Regression Release Gate)
- **Delta Analysis**: So sánh hiệu suất của Agent phiên bản mới với phiên bản cũ.
- **Auto-Gate**: Viết logic tự động quyết định có "phát hành" Agent mới hay "quay lại" phiên bản cũ dựa trên các chỉ số chất lượng, chi phí và hiệu năng.
- **Tại Sao Quan Trọng**: Trong thực tế, việc phát hành AI mới phải đảm bảo không làm giảm chất lượng; hệ thống này giúp kiểm soát rủi ro.

---

## 📤 Yêu Cầu Nộp Bài

Nhóm bạn cần nộp một repository (GitHub/GitLab) chứa đầy đủ các thành phần sau:

1. **Source Code**: Toàn bộ mã nguồn của hệ thống đánh giá.
2. **Reports**: 
   - `reports/summary.json`: Tóm tắt kết quả đánh giá.
   - `reports/benchmark_results.json`: Chi tiết kết quả benchmark (tạo ra sau khi chạy `main.py`).
3. **Group Report**: `analysis/failure_analysis.md` - Phân tích lỗi và giải pháp (phải điền đầy đủ).
4. **Individual Reports**: Các file `analysis/reflections/reflection_[Tên_SV].md` - Báo cáo cá nhân của từng thành viên.

**Lưu Ý**: Trước khi nộp, chạy `python check_lab.py` để kiểm tra định dạng. Nếu định dạng sai, script chấm điểm không chạy được và bị trừ điểm.

---

## 🏆 Bí Kíp Đạt Điểm Tối Đa

Để đạt điểm cao, tập trung vào những điểm sau:

- **Đánh Giá Retrieval (15%)**: Đừng chỉ đánh giá câu trả lời mà bỏ qua bước tìm kiếm. Bạn cần biết chunk nào gây ra lỗi để sửa đúng chỗ.
- **Độ Tin Cậy Của Multi-Judge (20%)**: Việc tin vào một giám khảo duy nhất là rủi ro. So sánh nhiều mô hình và tính độ tin cậy để chứng minh hệ thống khách quan.
- **Tối Ưu Hiệu Năng & Chi Phí (15%)**: Hệ thống phải chạy nhanh (bất đồng bộ) và báo cáo chi phí cho mỗi lần đánh giá. Đề xuất cách giảm 30% chi phí mà không giảm độ chính xác.
- **Phân Tích Nguyên Nhân Gốc Rễ (20%)**: Báo cáo "5 Whys" phải chỉ ra lỗi nằm ở ingestion pipeline, chunking strategy, retrieval, hay prompting.

---

## ⚠️ Lưu Ý Quan Trọng

- **Golden Dataset**: Phải chạy `python data/synthetic_gen.py` trước để tạo `data/golden_set.jsonl`. File này không được commit sẵn trong repo.
- **Bảo Mật**: File `.env` chứa API key **KHÔNG** được push lên GitHub.
- **Định Dạng**: Đảm bảo tất cả file theo đúng định dạng yêu cầu để tránh bị trừ điểm thủ tục.

Chúc nhóm bạn thành công trong việc xây dựng một hệ thống đánh giá AI mạnh mẽ và chuyên nghiệp! Nếu có câu hỏi, hãy thảo luận trong nhóm hoặc hỏi giảng viên.

==============================================

Kế Hoạch Phân Chia 6 Người
👥 Người 1: Data Lead - Dataset & SDG
Trách nhiệm:

Tạo data/synthetic_gen.py - script sinh 50+ test cases
Golden Dataset với Ground Truth IDs
Red Teaming cases (edge cases để "phá vỡ" hệ thống)
Mapping documents để tính Hit Rate
Output: data/golden_set.jsonl, data/test_cases/

👥 Người 2: Retrieval Specialist
Trách nhiệm:

Module đánh giá Retrieval (engine/retrieval_eval.py)
Tính toán Hit Rate và MRR
Phân tích chunk-level errors
Kết nối với Vector DB
Output: engine/retrieval_eval.py, metrics về retrieval quality

👥 Người 3 & 4: AI/Backend Engineers - Multi-Judge Engine
Trách nhiệm:

Xây dựng engine/llm_judge.py với 2+ judge models
Logic consensus (Agreement Rate, xử lý xung đột)
Calibration system
Người 3: Implement GPT-Judge + Claude-Judge
Người 4: Consensus logic + conflict resolution
Output: engine/llm_judge.py, consensus metrics

👥 Người 5: DevOps/Analyst - Regression Gate
Trách nối:

Module so sánh V1 vs V2 (engine/regression_gate.py)
Delta Analysis engine
Auto-Gate logic (Release/Rollback thresholds)
Báo cáo chi phí cho mỗi eval
Output: engine/regression_gate.py, regression report

👥 Người 6: Integration & Analysis Lead
Trách nhiệm:

Xây dựng async runner chính (main.py)
Tối ưu performance (< 2 phút cho 50 cases)
Tổng hợp reports (reports/summary.json, reports/benchmark_results.json)
Viết analysis/failure_analysis.md (5 Whys)
Output: main.py, reports, failure analysis

Timeline Thực Hiện
GIAI ĐOẠN 1 (45') - Tất cả bắt đầu
├── Người 1: Bắt đầu sinh Golden Dataset
├── Người 2: Setup Retrieval module
└── Người 3,4: Design Multi-Judge architecture
GIAI ĐOẠN 2 (90') - Development chính
├── Người 1: Hoàn thiện SDG (50+ cases)
├── Người 2: Retrieval eval metrics
├── Người 3,4: Implement Judge engines + consensus
├── Người 5: Regression gate
└── Người 6: Integration + async pipeline
GIAI ĐOẠN 3 (60') - Benchmark & Analysis
├── Cả team: Chạy benchmark
├── Người 2: Phân tích Retrieval errors
├── Người 6: Failure clustering + 5 Whys
└── Tất cả: Review kết quả
GIAI ĐOẠN 4 (45') - Hoàn thiện
├── Người 5: Regression report
├── Người 6: Tổng hợp báo cáo
├── Cả team: Chạy check_lab.py
└── Cá nhân: Viết reflection riêng
⚠️ Lưu Ý Quan Trọng
BẮT BUỘC phải có ít nhất 2 Judge models - không được dùng 1 Judge duy nhất (sẽ bị giới hạn 30 điểm)
Phải đánh giá Retrieval trước Generation
File .env không được push lên GitHub
Chạy python data/synthetic_gen.py TRƯỚC khi benchmark

==========================================================

Tóm tắt kế hoạch cho Thành viên 6 — Integration & Analysis Lead

Mục tiêu chính: Xây main.py (async runner), tích hợp các module retrieval/judge, tối ưu hiệu năng để chạy 50 cases < 2 phút, và tổng hợp báo cáo + phân tích lỗi sâu (5 Whys).

Các bước (và trạng thái):

Design async runner architecture: in-progress — xác định luồng thao tác, entry points, và interface với engine/retrieval_eval.py và engine/llm_judge.py.
Implement main.py async runner: not-started — chạy đồng thời các case, retry/backoff, timeouts, logging.
Integrate retrieval & judges: not-started — gọi hàm retrieval trước generation; hợp nhất kết quả judge để lấy consensus.
Optimize concurrency & perf: not-started — worker pool, batching, semaphore giới hạn API rate, đo thời gian từng bước.
Generate reports: not-started — sản xuất reports/summary.json và reports/benchmark_results.json (schema rõ ràng).
Failure clustering + 5 Whys: not-started — phân cụm lỗi và viết analysis/failure_analysis.md.
Final checks & run check_lab.py: not-started — đảm bảo định dạng và chạy kiểm thử cuối.
Tiêu chí chấp nhận (DoD) ngắn gọn:

main.py chạy toàn bộ golden set (50+ cases) trong < 2 phút trên môi trường dev nhóm.
Kết quả retrieval được tính trước generation cho mỗi case.
Reports tồn tại: reports/summary.json, reports/benchmark_results.json.
analysis/failure_analysis.md chứa kết quả clustering và 5 Whys cho top-5 lỗi.
Chạy python check_lab.py trả về exit code 0.
Checkpoint ngắn (làm trong 4 giai đoạn của lab):

Giai đoạn 1: hoàn thiện thiết kế async runner (30–45 phút).
Giai đoạn 2: implement + tích hợp (60–90 phút).
Giai đoạn 3: chạy benchmark, clustering, 5 Whys (45–60 phút).
Giai đoạn 4: tối ưu, báo cáo, chạy check_lab.py (30–45 phút).

**Kết quả chạy tích hợp (thành viên 6)**

- **Ngày chạy:** 2026-04-21
- **Tổng số test cases (golden set):** 1
- **Điểm trung bình (avg_score):** 4.5
- **Hit Rate (retrieval):** 100.0%
- **MRR:** (tính được từ báo cáo chi tiết) — 0.0
- **Agreement Rate (multi-judge):** 80.0%
- **Phiên bản Agent (metadata):** Agent_V2_Optimized
- **Trạng thái kiểm tra (`check_lab.py`):** Passed — tất cả file bắt buộc tồn tại và định dạng hợp lệ.

Ghi chú:

- Golden set hiện tại có 1 case mẫu vì script `data/synthetic_gen.py` được cấu hình tạo dữ liệu mẫu thay vì 50+ case. Trước khi chạy benchmark chính thức, hãy để `data/synthetic_gen.py` tạo >=50 test cases.
- `main.py` (đã thêm) thực hiện chạy bất đồng bộ, tính `hit_rate`, `mrr`, gọi `engine/llm_judge.py` để lấy `final_score` và `agreement_rate`, và ghi kết quả vào `reports/summary.json` và `reports/benchmark_results.json`.
- File phân tích lỗi đã tạo tại `analysis/failure_analysis.md` (chứa clustering sơ bộ và mẫu 5 Whys).

Tiếp theo (gợi ý):

- Chạy `python data/synthetic_gen.py` để tạo ít nhất 50 cases.
- Chạy `python main.py` để lấy benchmark hoàn chỉnh.
