import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from generation.answer_generator import AnswerGenerator
from evaluation.golden_dataset import GoldenDataset
from config.logging_config import setup_logging, get_logger

setup_logging(log_level = "INFO")
logger = get_logger(__name__)

DEFAULT_QUESTIONS = [
    "What is the main purpose of this document?",
    "Who created or authored this document?",
    "What are the key findings or conclusions?",
    "What methodology or approach was used?",
    "What are the main recommendations?",
    "What data sources were used?",
    "What are the limitations mentioned?",
    "What is the scope of this document?",
    "What problem does this document address?",
    "What are the next steps or future work mentioned?"
]

def load_questions_from_file(path: str) -> list:
    with open(path, "r", encoding = "utf-8") as f:
        return [
            line.strip()
            for line in f.readlines()
            if line.strip() and not line.startswith("#")
        ]
    
def generate_and_review(
    questions: list,
    auto_approve: bool = False
) -> list:
    generator = AnswerGenerator()
    approved = []
    total = len(questions)

    print(f"\n📋Generating answers for {total} questions...\n")

    for i, question in enumerate(questions, start = 1):
        print(f"[{i}/{total}] {question}")
        print("⏳ Running RAG pipeline...")

        try:
            response = generator.generate(
                query = question,
                use_query_rewriting = True,
                use_multi_query = True
            )

            print(f"✅ Answer: {response.answer[:120]}...")
            print(f"📄 Sources: {[s['source_file'] for s in response.sources]}")

            if auto_approve:
                approve = "y"
            else:
                approve = input("Add to golden dataset? [y/n]:").strip().lower()

            if approve == "y":
                contexts = [
                    chunk.content
                    for chunk in response.chunks_used
                ]
                source_files = list({
                    s["source_file"]
                    for s in response.sources
                })

                approved.append({
                    "question": question,
                    "ground_truth": response.answer,
                    "contexts": contexts,
                    "source_files": source_files,
                    "metadata": {
                        "rewritten_query": response.rewritten_query,
                        "total_tokens": response.total_tokens,
                        "cost_usd": response.cost_usd
                    }
                })
                print("✅ Added to golden dataset\n")
            else:
                print("⏭️ Skipped\n")

        except Exception as e:
            print(f"❌ Failed: {str(e)}\n")
            logger.error(
                "generate_golden_question_failed",
                question = question,
                error = str(e)
            )

    return approved

def main():
    parser = argparse.ArgumentParser(
        description = "Generate golden QA pairs for RAGAS Evaluation"
    )

    parser.add_argument(
        "--questions",
        type = str,
        default = None,
        help = "Path to text file with one question per line"
    )

    parser.add_argument(
        "--auto-approve",
        action = "store_true",
        help = "Auto-approve all generated answers (no manual review)"
    )

    parser.add_argument(
        "--output",
        type = str,
        default = None,
        help = "Custom output path for golden dataset JSON"
    )

    args = parser.parse_args()

    if args.questions:
        qpath = Path(args.questions)

        if not qpath.exists():
            print(f"❌ Questions file not found: {args.questions}")
            sys.exit(1)
        questions = load_questions_from_file(args.questions)
        print(f"📂 Loaded {len(questions)} questions from {args.questions}")

    else:
        questions = DEFAULT_QUESTIONS
        print(f"📋 Using {len(questions)} default seed questions")

    if not questions:
        print("❌ No questions to process.")
        sys.exit(1)

    approved = generate_and_review(
        questions = questions,
        auto_approve = args.auto_approve
    )

    if not approved:
        print("\n⚠️ No pairs approved. Golden dataset not updated.")
        sys.exit(0)

    dataset = GoldenDataset(
        dataset_path = args.output
    ) if args.output else GoldenDataset()

    added = dataset.add_pairs(approved)

    print("\n" + "="*50)
    print(f"✅ Added {added} new pairs to golden dataset")
    stats = dataset.get_stats()
    print(f"Total pairs now: {stats['total_pairs']}")
    print(f"Saved to: {stats['dataset_path']}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()