import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class GoldenQAPair:
    """
    A single ground-truth question-answer pair.
    Used as reference for RAGAS evaluation scoring.
    """
    question: str
    ground_truth: str
    contexts: List[str]
    source_file: List[str]
    metadata: dict = field(default_factory = dict)

class Golden_Dataset:
    """
    Loads, saves, and manages the golden QA dataset.
    """
    def __init__(self, dataset_path: str = None):
        self.dataset_path = Path(
            dataset_path or settings.golden_dataset_path
        )
        self.dataset_path.parent.mkdir(parents = True, exist_ok = True)

        logger.info(
            "golden_dataset_initialized",
            path=str(self.dataset_path)
        )

    def load(self) -> List[GoldenQAPair]:
        """
        Load golden QA pairs from disk.
        Returns empty list if file doesn't exist yet
        """
        if not self.dataset_path.exists():
            logger.warning(
                "golden_dataset_not_found",
                path = str(self.dataset_path)
            )
            return []
        
        try:
            with open(self.dataset_path, "r", encoding = "utf-8") as f:
                raw = json.load(f)

            pairs = [
                GoldenQAPair(
                    question = item["question"],
                    ground_truth = item["ground_truth"],
                    contexts = item.get("contexts", []),
                    source_file = item.get("source_files", item.get("source_file", [])),
                    metadata = item.get("metadata", {})
                )
                for item in raw
            ]

            logger.info(
                "golden_dataset_loaded",
                total_pairs = len(pairs)
            )
            return pairs
        
        except Exception as e:
            logger.error(
                "golden_dataset_load_failed",
                error = str(e)
            )
            raise

    def save(self, pairs: List[GoldenQAPair]) -> None:
        """
        Save golden QA pairs to disk as JSON.
        """
        data = [
            {
                "question": p.question,
                "ground_truth": p.ground_truth,
                "context": p.contexts,
                "source_file": p.source_file,
                "metadata": p.metadata
            }
            for p in pairs
        ]

        with open(self.dataset_path, "w", encoding = "utf-8") as f:
            json.dump(data, f, indent = 2, ensure_ascii = False)

        logger.info(
            "golden_dataset_saved",
            total_pairs = len(pairs),
            path = str(self.dataset_path)
        )

    def add_pairs(
        self,
        new_pairs: List[dict],
        deduplicate: bool = True
    ) -> int:
        """
        Add new QA pairs to the existing dataset.
        """
        existing = self.load()

        existing_questions = {
            p.question.strip().lower()
            for p in existing
        }

        added = 0
        for item in new_pairs:
            if isinstance(item, dict):
                question = item.get("question", "").strip()
                ground_truth = item.get("ground_truth", "").strip()
                contexts = item.get("contexts", [])
                source_files = item.get("source_files", [])
                metadata = item.get("metadata", {})
            else:
                question = item.question.strip()
                ground_truth = item.ground_truth.strip()
                contexts = item.contexts
                source_files = item.source_files
                metadata = item.metadata

            if not question or not ground_truth:
                continue

            if deduplicate and question.lower() in existing_questions:
                logger.debug(
                    "golden_pair_duplicate_skipped",
                    question_preview = question[:60]
                )
                continue

            existing.append(GoldenQAPair(
                question = question,
                ground_truth = ground_truth,
                contexts = contexts,
                source_files = source_files,
                metadata = metadata
            ))
            existing_questions.add(question.lower())
            added += 1

        self.save(existing)

        logger.info(
            "golden_pairs_added",
            added = added,
            total = len(existing)
        )
        return added
    
    def get_stats(self) -> dict:
        """
        Return basic stats about the golden dataset.
        """
        pairs = self.load()
        return {
            "total_pairs": len(pairs),
            "has_contexts": sum(1 for p in pairs if p.contexts),
            "has_source_files": sum(1 for p in pairs if p.source_files),
            "dataset_path": str(self.dataset_path)
        }