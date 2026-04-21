import asyncio
from engine.retrieval_eval import RetrievalEvaluator

async def main():
    print("🚀 Bắt đầu test RetrievalEvaluator...")
    evaluator = RetrievalEvaluator()
    
    # Tạo một số test case giả lập
    dataset = [
        {
            "question": "Mật khẩu quên thì phải làm sao?",
            "expected_retrieval_ids": ["it_helpdesk_faq"],
            "retrieved_ids": ["it_helpdesk_faq", "hr_leave_policy"] # Hit Rate: 1.0, MRR: 1.0
        },
        {
            "question": "SLA của sự cố P1 là bao lâu?",
            "expected_retrieval_ids": ["sla_p1_2026"],
            "retrieved_ids": ["access_control_sop", "sla_p1_2026"] # Hit Rate: 1.0, MRR: 0.5
        },
        {
            "question": "Xin nghỉ phép cần làm gì?",
            "expected_retrieval_ids": ["hr_leave_policy"],
            # Trả về kết quả sai hoàn toàn
            "retrieved_ids": ["access_control_sop", "policy_refund_v4"] # Hit Rate: 0.0, MRR: 0.0
        },
        {
            "question": "Câu hỏi không có retrieved_ids để test Mock VectorDB",
            "expected_retrieval_ids": ["dummy_doc_1"]
            # Không truyền retrieved_ids để hệ thống tự gọi mock VectorDB (trả về dummy_doc_1, dummy_doc_2)
            # -> Hit Rate: 1.0, MRR: 1.0
        }
    ]
    
    print("\nĐang chạy evaluate_batch...")
    results = await evaluator.evaluate_batch(dataset)
    
    print("\n📊 KẾT QUẢ TỔNG QUAN:")
    print(f"- Số lượng test cases: {results['total_evaluated']}")
    print(f"- Average Hit Rate: {results['avg_hit_rate']:.2f}")
    print(f"- Average MRR: {results['avg_mrr']:.2f}")
    
    print("\n🔍 PHÂN TÍCH LỖI CHUNK-LEVEL (2 case cuối):")
    for r in results['detailed_analysis'][-2:]:
        print(f"\nCâu hỏi: {r['question']}")
        print(f"Hit Rate: {r['hit_rate']} | MRR: {r['mrr']}")
        print(f"Lỗi: {r['errors']}")

if __name__ == "__main__":
    asyncio.run(main())
