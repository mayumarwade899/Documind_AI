import pytest
import json
from pathlib import Path
from evaluation.golden_dataset import GoldenDataset, GoldenQAPair

def test_golden_dataset_load_empty(tmp_path):
    """
    Loading non-existent dataset returns empty list.
    """
    dataset = GoldenDataset(
        dataset_path = str(tmp_path / "golden_qa.json")
    )
    pairs = dataset.load()
    assert pairs == []

def test_golden_dataset_save_and_load(tmp_path):
    """
    Saved pairs can be loaded back correctly.
    """
    dataset = GoldenDataset(
        dataset_path = str(tmp_path / "golden_qa.json")
    )
    pairs = [
        GoldenQAPair(
            question = "What is RAG?",
            ground_truth = "RAG is Retrieval Augmented Generation.",
            contexts = ["RAG combines retrieval with generation."],
            source_files = ["rag_paper.pdf"]
        )
    ]
    dataset.save(pairs)
    loaded = dataset.load()

    assert len(loaded) == 1
    assert loaded[0].question == "What is RAG?"
    assert loaded[0].ground_truth == "RAG is Retrieval Augmented Generation."

def test_golden_dataset_add_pairs(tmp_path):
    """
    Adding pairs increases dataset size.
    """
    dataset = GoldenDataset(
        dataset_path = str(tmp_path / "golden_qa.json")
    )
    new_pairs = [
        {
            "question": "What is BM25?",
            "ground_truth": "BM25 is a keyword ranking algorithm.",
            "contexts": [],
            "source_files": []
        }
    ]
    added = dataset.add_pairs(new_pairs)
    assert added == 1

    loaded = dataset.load()
    assert len(loaded) == 1

def test_golden_dataset_deduplication(tmp_path):
    """
    Duplicate questions are not added twice.
    """
    dataset = GoldenDataset(
        dataset_path = str(tmp_path / "golden_qa.json")
    )
    pair = {
        "question": "What is RAG?",
        "ground_truth": "RAG is Retrieval Augmented Generation.",
        "contexts": [],
        "source_files": []
    }
    dataset.add_pairs([pair])
    dataset.add_pairs([pair])

    loaded = dataset.load()
    assert len(loaded) == 1

def test_golden_dataset_stats(tmp_path):
    """
    Stats returns correct counts.
    """
    dataset = GoldenDataset(
        dataset_path = str(tmp_path / "golden_qa.json")
    )

    dataset.add_pairs([
        {
            "question": "Q1?",
            "ground_truth": "A1.",
            "contexts": ["context text"],
            "source_files": ["doc.pdf"]
        }
    ])

    stats = dataset.get_stats()
    assert stats["total_pairs"] == 1
    assert stats["has_contexts"] == 1
    assert stats["has_source_files"] == 1