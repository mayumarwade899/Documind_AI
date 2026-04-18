import sys
import time
from typing import Optional
from pathlib import Path

# Add project root to path for direct script execution
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.trulens_evaluator import TruLensEvaluator
from config.settings import get_settings
from config.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)
settings = get_settings()

def run_ci_gate(
    max_questions: Optional[int] = 6
) -> bool:
    print("\n" + "="*55)
    print("RAG SYSTEM — DYNAMIC CI QUALITY GATE")
    print("="*55)
    print(f"Mode: Fully Synthetic (Dynamic Discovery)")
    
    if max_questions:
        print(f"Limit: {max_questions} questions")

    print("\n⏳ Running TruLens evaluation suite...\n")

    try:
        evaluator = TruLensEvaluator()
        report = evaluator.evaluate(max_questions = max_questions)
    except Exception as e:
        print(f"\n❌ EVALUATION ERROR: {str(e)}")
        print("="*55 + "\n")
        logger.error("ci_gate_failed_execution", error=str(e))
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
    print(f"Dataset Size: {report.dataset_size} (Synthetic)")
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
        print("- Review document ingestion quality")
        print("- Check prompt instructions in prompt_builder.py")
        print("- Check judge LLM reasoning in detailed reports")

    print("="*55 + "\n")

    return all_passed

if __name__ == "__main__":
    max_q = 6
    if "--max" in sys.argv:
        try:
            idx = sys.argv.index("--max")
            max_q = int(sys.argv[idx + 1])
        except (ValueError, IndexError):
            pass

    passed = run_ci_gate(max_questions = max_q)

    sys.exit(0 if passed else 1)