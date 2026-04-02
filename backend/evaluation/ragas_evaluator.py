import time
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    context_relevancy,
    answer_correctness,
)

from evaluation.golden_dataset import GoldenDataset, GoldenQAPair
from generation.answer_generator import AnswerGenerator
from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class MetricScore:
    """
    Score for a single RAGAS metric.
    """
    name: str
    score: float
    passed: bool
    threshold: float

@dataclass
class EvaluationReport:
    """
    Complete RAGAS evaluation report.
    Saved to disk after every evaluation run.
    """
    run_id: str
    timestamp: str
    dataset_size: int

    faithfulness: MetricScore
    context_relevance: MetricScore
    answer_correctness: MetricScore

    overall_passed: bool 
    avg_score: float 
    evaluation_latency_ms: float

    per_question_scores: List[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

class RAGASEvaluator:
    """
    Runs RAGAS Evaluation on golden dataset
    """
    def __init__(
        self,
        generator: Optional[AnswerGenerator] = None,
        dataset: Optional[GoldenDataset]   = None,
        reports_dir: str = "data/evaluation_reports"
    ):
        self.generator = generator or AnswerGenerator()
        self.dataset = dataset   or GoldenDataset()
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents = True, exist_ok = True)

        self.min_faithfulness  = (
            settings.evaluation.min_faithfulness_score
        )
        self.min_context_rel   = (
            settings.evaluation.min_context_relevance_score
        )
        self.min_correctness   = (
            settings.evaluation.min_answer_correctness_score
        )

        logger.info(
            "ragas_evaluator_initialized",
            min_faithfulness = self.min_faithfulness,
            min_context_relevance = self.min_context_rel,
            min_correctness = self.min_correctness
        )

    def _run_rag_on_pairs(
        self,
        pairs: List[GoldenQAPair]
    ) -> List[dict]:
        """
        Run each golden question through the live RAG system.
        """
        results = []

        for i, pair in enumerate(pairs, start = 1):
            logger.info(
                "evaluating_question",
                index = i,
                total = len(pairs),
                question_preview = pair.question[:60]
            )

            try:
                rag_response = self.generator.generate(
                    query = pair.question,
                    use_query_rewriting = True,
                    use_multi_query = True
                )

                contexts = [
                    chunk.content
                    for chunk in rag_response.chunks_used
                ]

                if not contexts and pair.contexts:
                    contexts = pair.contexts

                results.append({
                    "question": pair.question,
                    "answer": rag_response.answer,
                    "contexts": contexts,
                    "ground_truth": pair.ground_truth
                })
            
            except Exception as e:
                logger.error(
                    "evaluation_question_failed",
                    question = pair.question[:60],
                    error = str(e)
                )

                results.append({
                    "question": pair.question,
                    "answer": "",
                    "contexts": pair.contexts or [],
                    "ground_truth": pair.ground_truth
                })

        return results
    
    def evaluate(
        self,
        max_questions: Optional[int] = None
    ) -> EvaluationReport:
        """
        Run full RAGAS evaluation against the golden dataset.
        """
        import uuid

        start_time = time.time()
        run_id = str(uuid.uuid4())[:8]

        logger.info(
            "ragas_evaluation_started",
            run_id = run_id,
            max_questions = max_questions
        )

        pairs = self.dataset.load()

        if not pairs:
            raise ValueError(
                "Golden dataset is empty. "
                "Add QA pairs to data/golden_dataset/golden_qa.json"
            )
        
        if max_questions:
            pairs = pairs[:max_questions]

        logger.info(
            "golden_dataset_loaded_for_eval",
            total_pairs = len(pairs)
        )

        rag_results = self._run_rag_on_pairs(pairs)
        eval_dataset = Dataset.from_list(rag_results)

        logger.info("running_ragas_metrics")

        try:
            ragas_result = self.evaluate(
                dataset = eval_dataset,
                metrics = [
                    faithfulness,
                    context_relevancy,
                    answer_correctness
                ]
            )
        except Exception as e:
            logger.error("ragas_evaluation_failed", error = str(e))
            raise

        scores_df = ragas_result.to_pandas()

        faith_score = float(scores_df["faithfulness"].mean())
        context_score = float(scores_df["context_relevancy"].mean())
        correct_score = float(scores_df["answer_correctness"].mean())
        avg_score = round(
            (faith_score + context_score + correct_score) / 3, 4
        )

        faithfulness_metric = MetricScore(
            name = "faithfulness",
            score = round(faith_score, 4),
            passed = faith_score >= self.min_faithfulness,
            threshold = self.min_faithfulness
        )

        context_metric = MetricScore(
            name = "context_relevance",
            score = round(context_score, 4),
            passed = context_score >= self.min_context_rel,
            threshold = self.min_context_rel
        )

        correctness_metric = MetricScore(
            name = "answer_correctness",
            score = round(correct_score, 4),
            passed = correct_score >= self.min_correctness,
            threshold = self.min_correctness
        )

        overall_passed = all([
            faithfulness_metric.passed,
            context_metric.passed,
            correctness_metric.passed
        ])

        per_question = scores_df.to_dict(orient = "records")
        latency_ms = round((time.time() - start_time) * 1000, 2)

        report = EvaluationReport(
            run_id = run_id,
            timestamp = datetime.utcnow().isoformat() + "Z",
            dataset_size = len(pairs),
            faithfulness = faithfulness_metric,
            context_relevance = context_metric,
            answer_correctness = correctness_metric,
            overall_passed = overall_passed,
            avg_score = avg_score,
            evaluation_latency_ms = latency_ms,
            per_question_scores = per_question
        )

        self._save_report(report)

        logger.info(
            "ragas_evaluation_complete",
            run_id = run_id,
            faithfulness = faith_score,
            context_relevance = context_score,
            answer_correctness = correct_score,
            overall_passed = overall_passed,
            latency_ms = latency_ms
        )

        return report
    
    def _save_report(self, report: EvaluationReport) -> None:
        """
        Save evaluation report as JSON to disk.
        """
        filename = (
            f"eval_{report.timestamp[:10]}_"
            f"{report.run_id}.json"
        )
        report_path = self.reports_dir / filename

        data = {
            "run_id": report.run_id,
            "timestamp": report.timestamp,
            "dataset_size": report.dataset_size,
            "overall_passed": report.overall_passed,
            "avg_score": report.avg_score,
            "metrics": {
                "faithfulness": {
                    "score": report.faithfulness.score,
                    "passed": report.faithfulness.passed,
                    "threshold": report.faithfulness.threshold
                },
                "context_relevance": {
                    "score": report.context_relevance.score,
                    "passed": report.context_relevance.passed,
                    "threshold": report.context_relevance.threshold
                },
                "answer_correctness": {
                    "score": report.answer_correctness.score,
                    "passed": report.answer_correctness.passed,
                    "threshold": report.answer_correctness.threshold
                }
            },
            "evaluation_latency_ms": report.evaluation_latency_ms,
            "per_question_scores": report.per_question_scores
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent = 2, ensure_ascii = False)

        logger.info(
            "evaluation_report_saved",
            path = str(report_path)
        )

        