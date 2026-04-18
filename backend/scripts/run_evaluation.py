import sys
import argparse
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.trulens_evaluator import TruLensEvaluator
from config.logging_config import setup_logging, get_logger

setup_logging(log_level="INFO")
logger = get_logger(__name__)

def print_report(report) -> None:
    print("\n" + "="*55)
    print("TRULENS DYNAMIC EVALUATION REPORT")
    print("="*55)
    print(f"Run ID: {report.run_id}")
    print(f"Timestamp: {report.timestamp}")
    print(f"Dataset size: {report.dataset_size} questions (Synthetic Suite)")
    print(f"Eval time: {report.evaluation_latency_ms/1000:.1f}s")
    print("\n  Metric Scores:")
    print("  " + "-"*50)

    metrics = [
        ("Faithfulness", report.faithfulness),
        ("Context Relevance", report.context_relevance),
        ("Answer Correctness", report.answer_correctness),
    ]

    for name, metric in metrics:
        status = "✅ PASS" if metric.passed else "❌ FAIL"
        bar_len = int(metric.score * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(
            f"{status} {name:<22} "
            f"[{bar}] {metric.score:.3f} "
            f"(min: {metric.threshold:.2f})"
        )

    print("  " + "-"*50)
    print(f"Average Score: {report.avg_score:.3f}")

    overall = "✅ ALL PASSED" if report.overall_passed else "❌ FAILED"
    print(f"Overall: {overall}")
    print("="*55 + "\n")

def main():
    parser = argparse.ArgumentParser(
        description = "Run TruLens-based dynamic evaluation on the RAG system"
    )

    parser.add_argument(
        "--max",
        type = int,
        default = 6,
        help = "Maximum number of questions to evaluate (default: 6)"
    )

    args = parser.parse_args()

    print(f"\n🚀 Starting Dynamic Evaluation (max {args.max} questions)...")
    print("Note: This suite is fully synthetic and generated on-the-fly from your documents.")

    try:
        evaluator = TruLensEvaluator()
        report = evaluator.evaluate(max_questions = args.max)
        print_report(report)
        
        if not report.overall_passed:
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Evaluation failed: {str(e)}")
        logger.error("evaluation_script_failed", error = str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()