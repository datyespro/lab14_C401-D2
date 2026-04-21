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

## 2. Engineering Contribution (Đóng góp Kỹ thuật) — 15đ

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

Đây là 2 metrics cốt lõi mà tôi chịu trách nhiệm, được thiết kế để chạy cho **50+ test cases** từ Golden Dataset:

- **Hit Rate@K:** Trả về `1.0` nếu ít nhất 1 document trong `expected_ids` xuất hiện trong top-K kết quả retrieval, ngược lại trả `0.0`. Đây là metric binary đơn giản nhưng rất trực quan — cho biết hệ thống retrieval có "tìm đúng" hay không.
- **MRR (Mean Reciprocal Rank):** Tính `1/rank` của document đúng đầu tiên tìm thấy trong danh sách retrieval. MRR nhạy hơn Hit Rate vì nó phân biệt được việc document đúng nằm ở vị trí 1 (MRR=1.0) hay vị trí 5 (MRR=0.2). Nếu không tìm thấy, MRR = 0.0.
- **Edge cases:** Cả hai hàm đều xử lý trường hợp `expected_ids` hoặc `retrieved_ids` rỗng, trả về 0.0 an toàn.

### 2.4. Phân tích Chunk-Level Errors

Hàm `analyze_chunk_errors()` cung cấp phân tích chi tiết ở cấp độ chunk — hỗ trợ trực tiếp cho nhóm Failure Analysis thực hiện phương pháp **"5 Whys"**:

- **Missing chunks:** Các document được kỳ vọng nhưng hệ thống retrieval không tìm được → nguyên nhân tiềm ẩn gây **mất thông tin** (information loss). Failure Analysis có thể truy vấn ngược: chunk bị miss là do Ingestion chưa ingest? Chunking strategy cắt sai? Hay embedding model encode kém?
- **Noise chunks:** Các document bị trả về nhưng không liên quan → nguyên nhân tiềm ẩn gây **hallucination** vì LLM sẽ dựa vào context sai.
- **Precision & Recall:** Tính toán thêm precision (tỉ lệ kết quả đúng trong tổng kết quả trả về) và recall (tỉ lệ kết quả đúng trong tổng kết quả kỳ vọng) để team Lead và Failure Analysis có con số cụ thể.
- **Perfect match flag:** `is_perfect_match = True` khi không có cả missing lẫn noise — dùng để nhanh chóng filter các case hoàn hảo khi phân tích batch lớn.

### 2.5. Xây dựng Scoring Wrapper & Batch Evaluation

- **`score()` method:** Được thiết kế để tương thích với `BenchmarkRunner` — nhận một test case và response, tự động query VectorDB nếu `retrieved_ids` chưa có, tính toán Hit Rate, MRR, chunk errors, và thêm cả proxy metrics cho faithfulness/relevancy bằng **Jaccard similarity** (keyword overlap). Điều này giúp pipeline đánh giá chạy được ngay cả khi không có RAGAS hoặc LLM Judge.
- **`evaluate_batch()` method:** Chạy eval cho toàn bộ dataset (50+ cases), tổng hợp `avg_hit_rate`, `avg_mrr`, và trả về `detailed_analysis` cho từng case. Method này hỗ trợ cả trường hợp case đã có sẵn `retrieved_ids` lẫn trường hợp cần tự query VectorDB.
- **Keyword-overlap proxy:** Hàm `_keyword_overlap()` sử dụng Jaccard similarity để ước lượng faithfulness (agent answer vs expected answer) và relevancy (agent answer vs question). Đây là proxy đơn giản nhưng hữu ích khi chạy offline — chi phí = 0.

### 2.6. Viết Test Suite (`test_retrieval.py`)

Tôi cũng xây dựng file `test_retrieval.py` để kiểm thử module:
- **4 test cases** bao phủ các tình huống: hit đúng vị trí 1, hit ở vị trí 2, miss hoàn toàn, và trường hợp thiếu `retrieved_ids` để kiểm tra Mock VectorDB tự query.
- Kết quả test giúp validate rằng cả Hit Rate, MRR, và chunk error analysis đều hoạt động đúng.

### 2.7. Chứng minh qua Git Commits

Các commit chính liên quan đến module retrieval:
- `engine/retrieval_eval.py` — Module chính, 329 dòng, 4 class (`LightweightKeywordDB`, `VectorDBConnection`, `RetrievalEvaluator`, và standalone test block).
- `test_retrieval.py` — File kiểm thử riêng với 4 test cases bao phủ các kịch bản.
- Tích hợp trực tiếp với `main.py` và `engine/runner.py` thông qua method `score()`.

---

## 3. Technical Depth (Chiều sâu Kỹ thuật) — 15đ

### 3.1. Giải thích MRR (Mean Reciprocal Rank)

**MRR** đo lường khả năng hệ thống retrieval xếp hạng document đúng ở vị trí cao nhất. Công thức:

```
MRR = (1/N) × Σ (1 / rank_i)
```

Trong đó `rank_i` là vị trí của document đúng đầu tiên trong kết quả retrieval của query thứ `i`.

**Ví dụ thực tế từ test_retrieval.py:**
- Query "SLA của sự cố P1?" → retrieved = `[access_control_sop, sla_p1_2026]`, expected = `[sla_p1_2026]` → document đúng ở vị trí 2 → MRR = 1/2 = **0.5**
- Query "Mật khẩu quên thì phải làm sao?" → retrieved = `[it_helpdesk_faq, ...]`, expected = `[it_helpdesk_faq]` → document đúng ở vị trí 1 → MRR = 1/1 = **1.0**

**Ý nghĩa thực tiễn:** MRR cao (gần 1.0) nghĩa là document đúng luôn nằm ở đầu danh sách → LLM nhận context chính xác ngay → giảm hallucination. MRR thấp (ví dụ 0.2) nghĩa là document đúng bị chìm xuống vị trí 5 → context window của LLM bị lấp đầy bởi noise trước → tăng nguy cơ hallucination.

### 3.2. Giải thích Cohen's Kappa

**Cohen's Kappa (κ)** đo mức độ **đồng thuận giữa 2 Judge** (hoặc 2 annotators), loại bỏ yếu tố đồng ý ngẫu nhiên. Công thức:

```
κ = (P_o - P_e) / (1 - P_e)
```

- `P_o` = tỉ lệ đồng thuận thực tế (observed agreement)
- `P_e` = tỉ lệ đồng thuận kỳ vọng do ngẫu nhiên (expected agreement by chance)

**Thang đánh giá:**
| κ | Mức độ đồng thuận |
|---|---|
| < 0.20 | Poor — Hai Judge gần như đánh giá ngẫu nhiên |
| 0.21–0.40 | Fair |
| 0.41–0.60 | Moderate |
| 0.61–0.80 | Substantial — Đáng tin cậy |
| 0.81–1.00 | Almost Perfect — Hai Judge rất nhất quán |

**Ý nghĩa trong hệ thống Multi-Judge:** Nếu 2 Judge (GPT-4o-mini và GPT-4o) cho điểm một test case lần lượt là 4/5 và 5/5, Cohen's Kappa giúp xác định xem sự khác biệt này có phải do thiên kiến của model hay chỉ là nhiễu ngẫu nhiên. κ thấp → cần calibrate lại prompt hoặc rubric; κ cao → kết quả Multi-Judge đáng tin cậy.

**Liên hệ với module Retrieval:** Retrieval metrics (Hit Rate, MRR) là **objective** (đúng/sai rõ ràng), trong khi Judge scores là **subjective**. Cohen's Kappa đo reliability của phần subjective, còn Hit Rate/MRR đo accuracy của phần objective — cả hai cùng đảm bảo toàn bộ pipeline evaluation đáng tin cậy.

### 3.3. Giải thích Position Bias

**Position Bias** là hiện tượng LLM Judge có xu hướng **đánh giá thiên lệch** dựa trên vị trí của thông tin trong context, thay vì dựa trên nội dung thực tế.

Có 2 loại Position Bias chính:
1. **Primacy Bias:** LLM ưu tiên thông tin ở **đầu** context → nếu document đúng nằm cuối danh sách retrieval, LLM có thể bỏ qua hoặc đánh giá thấp hơn.
2. **Recency Bias:** LLM ưu tiên thông tin ở **cuối** context → thông tin đầu bị lu mờ.

**Ảnh hưởng đến hệ thống eval:**
- **Phía Retrieval (module tôi phụ trách):** Position Bias giải thích tại sao MRR quan trọng hơn Hit Rate. Nếu document đúng nằm ở vị trí 5 (Hit Rate vẫn = 1.0), nhưng do Position Bias, LLM có thể không "nhìn thấy" nó → answer vẫn sai dù retrieval đã tìm đúng.
- **Phía Judge:** Khi Judge đánh giá câu trả lời dài, phần đầu hoặc phần cuối có thể được ưu tiên hơn → điểm không phản ánh chất lượng thực sự. Giải pháp: shuffle thứ tự context hoặc chạy Judge nhiều lần với thứ tự khác nhau rồi lấy trung bình.

**Kết luận:** Position Bias là lý do mạnh nhất để module Retrieval phải tối ưu **ranking quality** (MRR) chứ không chỉ tối ưu recall (Hit Rate). Document đúng phải nằm ở top-1 hoặc top-2 để giảm thiểu ảnh hưởng của Position Bias ở cả Generation lẫn Evaluation stage.

### 3.4. Trade-off giữa Chi phí và Chất lượng

| Phương pháp | Chi phí | Chất lượng Retrieval | Latency |
|---|---|---|---|
| **TF-IDF** (hiện tại) | $0 — chạy local | Trung bình — chỉ match keyword | <10ms/query |
| **BM25** | $0 — chạy local | Khá — xử lý term frequency tốt hơn | <10ms/query |
| **Dense Retrieval** (embedding) | $$ — cần API hoặc GPU | Cao — hiểu ngữ nghĩa | 50-200ms/query |
| **Hybrid** (BM25 + Dense) | $$$ — cả local lẫn API | Rất cao — kết hợp lexical + semantic | 100-300ms/query |

**Quyết định thiết kế:** Trong lab, tôi chọn TF-IDF vì:
1. **Chi phí = $0** — không cần API key, không cần GPU, không cần dịch vụ bên ngoài.
2. **Latency cực thấp** — đảm bảo toàn bộ pipeline eval 50+ cases chạy xong trong < 2 phút (yêu cầu Performance/Async).
3. **Deterministic** — kết quả reproducible, dễ debug hơn so với embedding-based retrieval.

**Khi lên production:** Cần chuyển sang Hybrid retrieval (BM25 + Dense) với VectorDB thật (Qdrant/Weaviate), chấp nhận chi phí cao hơn để có chất lượng retrieval tốt hơn → trực tiếp cải thiện Answer Quality. Kiến trúc `VectorDBConnection` wrapper đã sẵn sàng cho việc swap implementation này.

---

## 4. Problem Solving (Giải quyết Vấn đề) — 10đ

### 4.1. Không có VectorDB thật trong môi trường Lab
- **Vấn đề:** Các VectorDB như Chroma, Qdrant đòi hỏi cài đặt phức tạp và embedding model, không phù hợp chạy nhanh trong lab 4 tiếng. Nếu phụ thuộc VectorDB bên ngoài, nhóm có thể bị block hoàn toàn nếu dịch vụ không khả dụng.
- **Phân tích nguyên nhân:** Đây là bài toán về **environment dependency** — module evaluation không nên phụ thuộc vào infrastructure ngoài scope kiểm soát.
- **Giải pháp:** Thiết kế `LightweightKeywordDB` với TF-IDF — không cần GPU, không cần API, chạy offline hoàn toàn. Dùng pattern **Strategy/Adapter** để khi nhóm có VectorDB thật, chỉ cần swap implementation bên trong `VectorDBConnection` mà không ảnh hưởng code gọi bên ngoài.
- **Kết quả:** Toàn nhóm có thể chạy `python main.py` và `python check_lab.py` ngay lập tức mà không cần setup bất kỳ dịch vụ nào.

### 4.2. Đảm bảo tính tương thích với pipeline async
- **Vấn đề:** `main.py` chạy hoàn toàn bất đồng bộ với `asyncio`, nhưng TF-IDF scoring là CPU-bound synchronous.
- **Phân tích nguyên nhân:** Nếu gọi synchronous function trực tiếp trong async pipeline, event loop sẽ bị block → các task khác (Multi-Judge API calls) phải chờ → bottleneck.
- **Giải pháp:** Sử dụng `asyncio.to_thread()` để offload TF-IDF computation sang thread pool, tránh block event loop. Method `query_async()` wrap `query()` synchronous một cách transparent.
- **Kết quả:** Pipeline async chạy mượt, retrieval eval không block Multi-Judge và các module khác.

### 4.3. Xử lý Unicode / Tiếng Việt
- **Vấn đề:** Tokenizer đơn giản có thể gặp vấn đề với dấu tiếng Việt và ký tự đặc biệt. Golden Dataset chứa câu hỏi tiếng Việt có dấu, nếu tokenizer không xử lý đúng sẽ dẫn đến TF-IDF score sai.
- **Giải pháp:** Sử dụng regex với flag `re.UNICODE` và đọc file với encoding `utf-8`, đảm bảo hoạt động đúng với corpus tiếng Việt.
- **Kết quả:** Tokenizer tách đúng các từ tiếng Việt có dấu, TF-IDF scoring hoạt động chính xác.

### 4.4. Thiết kế Interface tương thích BenchmarkRunner
- **Vấn đề:** Module `engine/runner.py` (do thành viên khác phát triển) cần gọi retrieval eval nhưng interface chưa được thống nhất ban đầu.
- **Giải pháp:** Thiết kế method `score(case, response)` → trả về dict chuẩn chứa cả retrieval metrics lẫn proxy faithfulness/relevancy. Format output tương thích với cả `regression_gate.py` lẫn `reports/benchmark_results.json`.
- **Kết quả:** Tích hợp thành công — `main.py` gọi `RetrievalEvaluator.score()` trực tiếp, kết quả chảy liền mạch vào pipeline.

---

## 5. Mối liên hệ giữa Retrieval Quality và Answer Quality

> *Rubric yêu cầu: "Giải thích được mối liên hệ giữa Retrieval Quality và Answer Quality."*

Trong pipeline RAG (Retrieval-Augmented Generation), chất lượng câu trả lời phụ thuộc **trực tiếp** vào chất lượng retrieval:

```
[Query] → [Retrieval] → [Context] → [LLM Generation] → [Answer]
              ↑                            ↑
         Hit Rate, MRR              Faithfulness, Relevancy
```

1. **Retrieval đúng → Answer tốt:** Nếu Hit Rate = 1.0 và MRR = 1.0, LLM nhận được context chính xác ở vị trí đầu → câu trả lời faithful (không hallucinate) và relevant (đúng trọng tâm).

2. **Retrieval sai → Hallucination:** Nếu Hit Rate = 0.0 (không tìm được document đúng), LLM buộc phải sinh câu trả lời từ noise chunks hoặc parametric knowledge → rất dễ hallucinate.

3. **Retrieval đúng nhưng rank thấp → Position Bias:** Nếu Hit Rate = 1.0 nhưng MRR = 0.2 (document đúng ở vị trí 5), LLM có thể ưu tiên noise ở vị trí 1-4 do Position Bias → answer vẫn kém dù retrieval "tìm được".

**Kết luận:** Đánh giá Retrieval phải đi trước đánh giá Generation. Nếu Retrieval đã sai, việc đánh giá Answer Quality (Faithfulness, Accuracy) là vô nghĩa vì lỗi nằm ở upstream. Module `retrieval_eval.py` của tôi cung cấp chính xác dữ liệu này để nhóm biết **lỗi nằm ở Retrieval hay Generation**.

---

## 6. Kết quả đạt được

| Metric | Kết quả |
|---|---|
| ✅ Module `retrieval_eval.py` | Hoàn chỉnh — 329 dòng code, 4 class chính |
| ✅ Hit Rate & MRR | Tính toán chính xác cho 50+ test cases, handle edge cases |
| ✅ Chunk-level error analysis | Phân tách missing/noise chunks + precision/recall |
| ✅ VectorDB connection | Hoạt động offline (TF-IDF) + sẵn sàng plug-in production DB |
| ✅ Async support | Tương thích pipeline bất đồng bộ, không block event loop |
| ✅ Test suite | 4 test cases pass thành công (`test_retrieval.py`) |
| ✅ Tích hợp | Được `main.py` và `BenchmarkRunner` gọi trực tiếp |
| ✅ Chi phí eval | $0 — toàn bộ retrieval eval chạy offline, không tốn API |

---

## 7. Đề xuất cải tiến (Next Steps)

- **Semantic search:** Tích hợp embedding model (ví dụ `sentence-transformers`) để thay thế TF-IDF, nâng cao chất lượng retrieval.
- **NDCG metric:** Bổ sung Normalized Discounted Cumulative Gain để đánh giá toàn diện hơn thứ tự ranking.
- **Retrieval-Generation correlation:** Phân tích mối tương quan giữa retrieval quality (Hit Rate/MRR) và generation quality (Faithfulness/Relevancy) bằng scatter plot để chứng minh giả thuyết "retrieval tốt → answer tốt".
- **Position Bias mitigation:** Shuffle thứ tự retrieved chunks và chạy evaluation nhiều lần để giảm ảnh hưởng Position Bias.
- **A/B testing framework:** So sánh nhiều retrieval strategy (BM25, TF-IDF, Dense Retrieval, Hybrid) trên cùng golden dataset.

---

*Module `engine/retrieval_eval.py` là nền tảng để toàn bộ hệ thống evaluation có thể đo lường và cải thiện chất lượng AI Agent một cách khoa học — đúng tinh thần "Nếu bạn không thể đo lường nó, bạn không thể cải thiện nó."*
