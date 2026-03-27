import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.pipeline import IngestionPipeline
from config.logging_config import setup_logging, get_logger

setup_logging(log_level="INFO")
logger = get_logger(__name__)

def print_result(result) -> None:
    """
    Print ingestion result in a clean readable format.
    """
    print("\n" + "="*55)
    print("INGESTION COMPLETE")
    print("="*55)
    print(f"Total files: {result.total_files}")
    print(f"Successful: {result.successful_files}")
    print(f"Failed: {result.failed_files}")
    print(f"Skipped (dup): {result.skipped_files}")
    print(f"Total chunks: {result.total_chunks}")
    print(f"Total pages: {result.total_pages}")
    print(f"Time taken: {result.total_latency_ms/1000:.2f}s")

    if result.file_results:
        print("\n  File Details:")
        print("  " + "-"*50)
        for fr in result.file_results:
            status = "✅" if fr["success"] else "❌"
            skip = "(skipped)" if fr.get("skipped") else ""
            print(
                f"{status} {fr['filename']}{skip}"
                f" — {fr['chunks']} chunks"
                f" | {fr['pages']} pages"
                f" | {fr['latency_ms']}ms"
            )
            if fr.get("error"):
                print(f"Error: {fr['error']}")

    if result.errors:
        print("\n Errors:")
        for err in result.errors:
            print(f"❌ {err['filename']}: {err['error']}")

    print("="*55 + "\n")

def main():
    parser = argparse.ArgumentParser(
        description = "Ingest documents into the RAG system"
    )
    parser.add_argument(
        "--file",
        type = str,
        help = "Path to a single document file"
    )

    parser.add_argument(
        "--dir",
        type = str,
        default = "data/documents",
        help = "Path to directory of documents (default: data/documents)"
    )

    parser.add_argument(
        "--force",
        action = "store_true",
        help = "Force re-ingestion even if document already exists"
    )

    args = parser.parse_args()

    print("\n🚀 Initializing ingestion pipeline...")
    pipeline = IngestionPipeline()

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ File not found: {args.file}")
            sys.exit(1)

        print(f"📄 Ingesting file: {file_path.name}")
        result = pipeline.ingest_file(
            str(file_path),
            force_reingest = args.force
        )
    else:
        dir_path = Path(args.dir)
        if not dir_path.exists():
            print(f"❌ Directory not found: {args.dir}")
            sys.exit(1)

        files = list(dir_path.iterdir())
        supported = [
            f for f in files
            if f.suffix.lower() in {".pdf", ".txt", ".docx"}
        ]

        if not supported:
            print(f"❌ No supported files found in: {args.dir}")
            print("Supported: .pdf, .txt, .docx")
            sys.exit(1)

        print(f"📁 Ingesting directory: {args.dir}")
        print(f"Found {len(supported)} supported files")

        result = pipeline.ingest_directory(
            str(dir_path),
            force_reingest = args.force
        )

    print_result(result)

    if result.failed_files > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()