import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.ragas_evaluator import RAGASEvaluator
from evaluation.golden_dataset import GoldenDataset
from monitoring.feedback_store import FeedbackStore
from config.logging_config import setup_logging, get_logger

setup_logging(log_level="INFO")
logger = get_logger(__name__)

def add_feedback_to_golden(days: int = 30) -> None:
    """
    Export positive feedback as golden QA pairs.
    Run this before evaluation to grow the dataset.
    """
    print(f"\n📥 Exporting positive feedback (last {days} days)...")

    store = FeedbackStore()
    golden = GoldenDataset()
    pairs = store.export_as_golden_pairs(
        days = days,
        only_positive = True
    )

    if not pairs:
        print("No positive feedback found to export.")
        return
    
    added = golden.add_pairs(pairs)
    print(f"✅ Added {added} new pairs to golden dataset")
    stats = golden.get_stats()
    print(f"Total pairs now: {stats['total_pairs']}")

def print_report(report) -> None:
    """
    Print evaluation report in readable format.
    """
    print("\n" + "="*55)
    print("RAGAS EVALUATION REPORT")
    print("="*55)
    print(f"Run ID: {report.run_id}")
    print(f"Timestamp: {report.timestamp}")
    print(f"Dataset size: {report.dataset_size} questions")
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
            f"[{bar}] {metric.score:.3f}"
            f"(min: {metric.threshold:.2f})"
        )

    print("  " + "-"*50)
    print(f"Average Score: {report.avg_score:.3f}")

    overall = "✅ ALL PASSED" if report.overall_passed else "❌ FAILED"
    print(f"Overall: {overall}")
    print("="*55 + "\n")

def main():
    parser = argparse.ArgumentParser(
        description = "Run RAGAS evaluation on the RAG system"
    )

    parser.add_argument(
        "--max",
        type = int,
        default = None,
        help = "Limit evaluation to first N questions (for quick test)"
    )

    parser.add_argument(
        "--feedback-days",
        type = int,
        default = 30,
        help = "Days of feedback to export (default: 30)"
    )

    parser.add_argument(
        "--stats",
        action = "store_true",
        help = "Just show golden dataset stats, no evaluation"
    )

    args = parser.parse_args()

    if args.stats:
        dataset = GoldenDataset()
        stats = dataset.get_stats()
        print("\n📋 Golden Dataset Stats")
        print("="*40)
        print(f"Total pairs: {stats['total_pairs']}")
        print(f"With contexts: {stats['has_contexts']}")
        print(f"With sources: {stats['has_source_files']}")
        print(f"Path: {stats['dataset_path']}")
        print("="*40 + "\n")
        return
    
    if args.add_feedback:
        add_feedback_to_golden(days = args.feedback_days)

    dataset = GoldenDataset()
    stats = dataset.get_stats()

    if stats["total_pairs"] == 0:
        print("\n❌ Golden dataset is empty.")
        print("Options:")
        print("1.Run with --add-feedback to import from feedback")
        print(
            "2.Manually add pairs to: "
            f"{stats['dataset_path']}"
        )
        print(
            "3.Run scripts/generate_golden.py "
            "to auto-generate pairs"
        )
        sys.exit(1)
    
    print(
        f"\n📋 Running evaluation on "
        f"{stats['total_pairs']} golden pairs..."
    )

    if args.max:
        print(f"(Limited to first {args.max} questions)")

    try:
        evaluator = RAGASEvaluator()
        report = evaluator.evaluate(max_questions = args.max)
    except Exception as e:
        print(f"\n❌ Evaluation failed: {str(e)}")
        logger.error("evaluation_script_failed", error = str(e))
        sys.exit(1)

    print_report(report)

    if not report.overall_passed:
        sys.exit(1)

if __name__ == "__main__":
    main()