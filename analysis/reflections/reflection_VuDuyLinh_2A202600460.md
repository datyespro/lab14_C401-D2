# 📑 Individual Reflection — Retrieval Specialist (Người 2)

**Họ và tên:** Vũ Duy Linh  
**Mã số học viên:** 2A202600460  
**Vai trò:** Retrieval Specialist  
**Ngày hoàn thành:** 2026-04-21

---

## 1. Mục tiêu và Trách nhiệm

Vai trò của tôi trong nhóm là **Retrieval Specialist** — chịu trách nhiệm xây dựng module đánh giá chất lượng Retrieval (`engine/retrieval_eval.py`). Đây là nền tảng quan trọng nhất trong pipeline đánh giá, vì nếu giai đoạn Retrieval trả về sai tài liệu, thì dù Generation có tốt đến đâu, câu trả lời cuối cùng vẫn sẽ bị hallucination hoặc thiếu thông tin.

Cụ thể, tôi được giao 4 nhiệm vụ chính:
1. Thiết kế và triển khai module `engine/retrieval_eval.py`.
2. Tính toán các metrics **Hit Rate** và **MRR** (Mean Reciprocal Rank).
3. Phân tích lỗi cấp độ chunk (chunk-level error analysis).
4. Kết nối với Vector Database để lấy kết quả retrieval và đối chiếu với ground truth.

---

## 2. Chi tiết Công việc đã thực hiện

### 2.1. Xây dựng Vector DB Connection (`VectorDBConnection` & `LightweightKeywordDB`)

Thách thức đầu tiên là thiết kế lớp kết nối Vector DB sao cho **linh hoạt** — chạy được cả offline (lab) lẫn production.

- **Quyết định thiết kế quan trọng:** Thay vì phụ thuộc hoàn toàn vào một VectorDB bên ngoài (Chroma, Qdrant, Weaviate…), tôi xây dựng class `LightweightKeywordDB` — một mock VectorDB hoạt động dựa trên **TF-IDF scoring** trên corpus tài liệu từ `data/documents/*.txt`. Điều này cho phép toàn bộ nhóm chạy evaluation mà không cần khởi động bất kỳ dịch vụ DB nào.
- **Backward compatibility:** Class `VectorDBConnection` đóng vai trò **shim/wrapper**, delegate mọi query về `LightweightKeywordDB`, đồng thời giữ interface `connect()` / `query()` chuẩn để khi chuyển sang VectorDB thật (production), chỉ cần thay thế implementation bên trong mà không ảnh hưởng code gọi bên ngoài.
- **Fallback corpus:** Nếu thư mục `data/documents/` trống hoặc chưa có dữ liệu, hệ thống tự sinh 3 documents giả lập (`policy_handbook`, `user_guide`, `faq`) để đảm bảo test luôn chạy được.

### 2.2. Triển khai TF-IDF Indexing Engine

Module `LightweightKeywordDB` tự xử lý toàn bộ pipeline NLP đơn giản:

- **Tokenization:** Tách từ bằng regex (`\w+`), lowercase, loại bỏ token ngắn (≤1 ký tự). Hỗ trợ Unicode nên hoạt động tốt với tiếng Việt.
- **TF (Term Frequency):** Tính tần suất chuẩn hóa cho mỗi term trong từng document.
- **IDF (Inverse Document Frequency):** Sử dụng công thức `log((N+1)/(df+1)) + 1` (smooth IDF) để tránh chia cho 0 và giảm ảnh hưởng của các từ quá phổ biến.
- **Scoring & Ranking:** Query được tokenize, rồi tính tổng TF-IDF score cho mỗi document, sắp xếp giảm dần và trả về `top_k` kết quả.
- **Async support:** Wrap hàm `query()` synchronous bằng `asyncio.to_thread()` để không block event loop khi chạy trong pipeline bất đồng bộ của `main.py`.

### 2.3. Tính toán Hit Rate và MRR

Đây là 2 metrics cốt lõi mà tôi chịu trách nhiệm:

- **Hit Rate@K:** Trả về `1.0` nếu ít nhất 1 document trong `expected_ids` xuất hiện trong top-K kết quả retrieval, ngược lại trả `0.0`. Đây là metric binary đơn giản nhưng rất trực quan — cho biết hệ thống retrieval có "tìm đúng" hay không.
- **MRR (Mean Reciprocal Rank):** Tính `1/rank` của document đúng đầu tiên tìm thấy trong danh sách retrieval. MRR nhạy hơn Hit Rate vì nó phân biệt được việc document đúng nằm ở vị trí 1 (MRR=1.0) hay vị trí 5 (MRR=0.2). Nếu không tìm thấy, MRR = 0.0.
- **Edge cases:** Cả hai hàm đều xử lý trường hợp `expected_ids` hoặc `retrieved_ids` rỗng, trả về 0.0 an toàn.

### 2.4. Phân tích Chunk-Level Errors

Hàm `analyze_chunk_errors()` cung cấp phân tích chi tiết ở cấp độ chunk:

- **Missing chunks:** Các document được kỳ vọng nhưng hệ thống retrieval không tìm được → nguyên nhân tiềm ẩn gây **mất thông tin** (information loss).
- **Noise chunks:** Các document bị trả về nhưng không liên quan → nguyên nhân tiềm ẩn gây **hallucination** vì LLM sẽ dựa vào context sai.
- **Precision & Recall:** Tính toán thêm precision (tỉ lệ kết quả đúng trong tổng kết quả trả về) và recall (tỉ lệ kết quả đúng trong tổng kết quả kỳ vọng) để team Lead và Failure Analysis có con số cụ thể.
- **Perfect match flag:** `is_perfect_match = True` khi không có cả missing lẫn noise — dùng để nhanh chóng filter các case hoàn hảo khi phân tích batch lớn.

### 2.5. Xây dựng Scoring Wrapper & Batch Evaluation

- **`score()` method:** Được thiết kế để tương thích với `BenchmarkRunner` — nhận một test case và response, tự động query VectorDB nếu `retrieved_ids` chưa có, tính toán Hit Rate, MRR, chunk errors, và thêm cả proxy metrics cho faithfulness/relevancy bằng **Jaccard similarity** (keyword overlap). Điều này giúp pipeline đánh giá chạy được ngay cả khi không có RAGAS hoặc LLM Judge.
- **`evaluate_batch()` method:** Chạy eval cho toàn bộ dataset, tổng hợp `avg_hit_rate`, `avg_mrr`, và trả về `detailed_analysis` cho từng case. Method này hỗ trợ cả trường hợp case đã có sẵn `retrieved_ids` lẫn trường hợp cần tự query VectorDB.
- **Keyword-overlap proxy:** Hàm `_keyword_overlap()` sử dụng Jaccard similarity để ước lượng faithfulness (agent answer vs expected answer) và relevancy (agent answer vs question). Đây là proxy đơn giản nhưng hữu ích khi chạy offline.

### 2.6. Viết Test Suite (`test_retrieval.py`)

Tôi cũng xây dựng file `test_retrieval.py` để kiểm thử module:
- **4 test cases** bao phủ các tình huống: hit đúng vị trí 1, hit ở vị trí 2, miss hoàn toàn, và trường hợp thiếu `retrieved_ids` để kiểm tra Mock VectorDB tự query.
- Kết quả test giúp validate rằng cả Hit Rate, MRR, và chunk error analysis đều hoạt động đúng.

---

## 3. Kết quả đạt được

| Metric | Kết quả |
|---|---|
| ✅ Module `retrieval_eval.py` | Hoàn chỉnh — 329 dòng code, 4 class chính |
| ✅ Hit Rate & MRR | Tính toán chính xác, handle edge cases |
| ✅ Chunk-level error analysis | Phân tách missing/noise chunks + precision/recall |
| ✅ VectorDB connection | Hoạt động offline (TF-IDF) + sẵn sàng plug-in production DB |
| ✅ Async support | Tương thích pipeline bất đồng bộ của nhóm |
| ✅ Test suite | 4 test cases pass thành công |
| ✅ Tích hợp | Được `main.py` và `BenchmarkRunner` gọi trực tiếp |

---

## 4. Khó khăn và Cách giải quyết

### 4.1. Không có VectorDB thật trong môi trường Lab
- **Vấn đề:** Các VectorDB như Chroma, Qdrant đòi hỏi cài đặt phức tạp và embedding model, không phù hợp chạy nhanh trong lab 4 tiếng.
- **Giải pháp:** Thiết kế `LightweightKeywordDB` với TF-IDF — không cần GPU, không cần API, chạy offline hoàn toàn. Dùng pattern **Strategy/Adapter** để khi nhóm có VectorDB thật, chỉ cần swap implementation.

### 4.2. Đảm bảo tính tương thích với pipeline async
- **Vấn đề:** `main.py` chạy hoàn toàn bất đồng bộ với `asyncio`, nhưng TF-IDF scoring là CPU-bound.
- **Giải pháp:** Sử dụng `asyncio.to_thread()` để offload TF-IDF computation sang thread pool, tránh block event loop.

### 4.3. Xử lý Unicode / Tiếng Việt
- **Vấn đề:** Tokenizer đơn giản có thể gặp vấn đề với dấu tiếng Việt và ký tự đặc biệt.
- **Giải pháp:** Sử dụng regex với flag `re.UNICODE` và đọc file với encoding `utf-8`, đảm bảo hoạt động đúng với corpus tiếng Việt.

---

## 5. Bài học rút ra

1. **Retrieval is the foundation:** Qua lab này tôi hiểu sâu hơn rằng trong pipeline RAG, nếu Retrieval sai thì mọi thứ phía sau đều vô nghĩa. Metrics như Hit Rate và MRR là cách đo lường khách quan nhất để phát hiện vấn đề sớm.

2. **MRR nhạy hơn Hit Rate:** Hit Rate chỉ cho biết "có tìm được hay không", trong khi MRR cho biết "tìm được ở vị trí nào". Trong thực tế, document đúng nằm ở vị trí 1 vs vị trí 5 có ảnh hưởng rất lớn đến chất lượng context mà LLM nhận được, vì context window có giới hạn.

3. **Design for flexibility:** Việc tách interface (VectorDBConnection) khỏi implementation (LightweightKeywordDB) giúp nhóm chạy lab suôn sẻ, đồng thời sẵn sàng cho production mà không cần refactor.

4. **Chunk error analysis giúp Root Cause Analysis:** Khi biết chính xác chunk nào bị missing và chunk nào là noise, nhóm Failure Analysis có thể truy ngược lại nguyên nhân gốc rễ — là do chunking strategy, embedding model, hay query formulation.

5. **Trade-off giữa Chi phí và Chất lượng:** TF-IDF không chính xác bằng semantic search (embedding-based), nhưng chi phí bằng 0 và latency cực thấp. Trong môi trường lab, đây là trade-off hợp lý. Trong production, cần chuyển sang VectorDB thật với embedding model phù hợp.

---

## 6. Đề xuất cải tiến (Next Steps)

- **Semantic search:** Tích hợp embedding model (ví dụ `sentence-transformers`) để thay thế TF-IDF, nâng cao chất lượng retrieval.
- **NDCG metric:** Bổ sung Normalized Discounted Cumulative Gain để đánh giá toàn diện hơn thứ tự ranking.
- **Retrieval-Generation correlation:** Phân tích mối tương quan giữa retrieval quality (Hit Rate/MRR) và generation quality (Faithfulness/Relevancy) để chứng minh giả thuyết "retrieval tốt → answer tốt".
- **A/B testing framework:** So sánh nhiều retrieval strategy (BM25, TF-IDF, Dense Retrieval, Hybrid) trên cùng golden dataset.

---

*Module `engine/retrieval_eval.py` là nền tảng để toàn bộ hệ thống evaluation có thể đo lường và cải thiện chất lượng AI Agent một cách khoa học.*
