import sys
from typing import Optional

from evaluation.ragas_evaluator import RAGASEvaluator
from evaluation.golden_dataset import GoldenDataset
from config.settings import get_settings
from config.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)
settings = get_settings()

def run_ci_gate(
    max_questions: Optional[int] = None
) -> bool:
    print("\n" + "="*55)
    print("RAG SYSTEM — CI QUALITY GATE")
    print("="*55)

    dataset = GoldenDataset
    stats = dataset.get_stats()

    if stats["total_pairs"] == 0:
        print("\n❌ FAILED: Golden dataset is empty.")
        print(f"Add QA pairs to: {stats['dataset_path']}")
        print("="*55 + "\n")
        return False
    
    print(f"\n📋 Golden dataset: {stats['total_pairs']} QA pairs")

    if max_questions:
        print(f"(Running on first {max_questions} only)")

    print("\n⏳ Running RAGAS evaluation...\n")

    try:
        evaluator = RAGASEvaluator()
        report = evaluator.evaluate(max_questions = max_questions)
    except Exception as e:
        print(f"\n❌ EVALUATION ERROR: {str(e)}")
        print("="*55 + "\n")
        return False

    print("\n📊 EVALUATION RESULTS")
    print("-"*55)

    metrics = [
        ("Faithfulness", report.faithfulness),
        ("Context Relevance", report.context_relevance),
        ("Answer Correctness", report.answer_correctness),
    ]

    all_passed = True
    for name, metric in metrics:
        status = "✅ PASS" if metric.passed else "❌ FAIL"
        print(
            f"{status}  {name:<22} "
            f"score={metric.score:.3f}  "
            f"threshold = {metric.threshold:.2f}"
        )
        if not metric.passed:
            all_passed = False

    print("-"*55)
    print(f"Average Score: {report.avg_score:.3f}")
    print(f"Dataset Size: {report.dataset_size} questions")
    print(
        f"Eval Time: "
        f"{report.evaluation_latency_ms/1000:.1f}s"
    )
    print("-"*55)

    if all_passed:
        print("\n✅ ALL METRICS PASSED — deployment approved")
    else:
        print("\n❌ QUALITY GATE FAILED — deployment blocked")
        print("\nFix:")
        print("- Review retrieval quality")
        print("- Check prompt instructions")
        print("- Add more golden pairs to improve coverage")

    print("="*55 + "\n")

    return all_passed

if __name__ == "__main__":
    max_q = None
    if "--max" in sys.argv:
        idx = sys.argv.index("--max")
        max_q = int(sys.argv[idx + 1])

    passed = run_ci_gate(max_questions = max_q)

    sys.exit(0 if passed else 1)