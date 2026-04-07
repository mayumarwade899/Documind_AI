import time
import uuid
from typing import List
from collections import namedtuple

from config.settings import get_settings
from config.logging_config import get_logger
from api.dependencies import get_answer_generator
from monitoring.feedback_store import FeedbackStore

logger = get_logger(__name__)
settings = get_settings()

MetricResult = namedtuple("MetricResult", ["score", "passed", "threshold"])

class EvaluationReport:
    def __init__(
        self,
        run_id: str,
        timestamp: str,
        dataset_size: int,
        faithfulness: MetricResult,
        context_relevance: MetricResult,
        answer_correctness: MetricResult,
        overall_passed: bool,
        avg_score: float,
        evaluation_latency_ms: float
    ):
        self.run_id = run_id
        self.timestamp = timestamp
        self.dataset_size = dataset_size
        self.faithfulness = faithfulness
        self.context_relevance = context_relevance
        self.answer_correctness = answer_correctness
        self.overall_passed = overall_passed
        self.avg_score = avg_score
        self.evaluation_latency_ms = evaluation_latency_ms

class TruLensEvaluator:
    def __init__(self):
        self.generator = get_answer_generator()
        self.thresholds = {
            "faithfulness": 0.7,
            "context_relevance": 0.7,
            "answer_correctness": 0.6,
        }

    def _get_historical_queries(self, max_questions: int = 5) -> List[str]:
        """Fetch real user questions uniquely to test the pipeline reference-free."""
        store = FeedbackStore()
        records = store._load_recent_records(days=30)
        
        # We only need the queries since this is reference-free
        unique_queries = list({r.get("query") for r in records if r.get("query")})

        if not unique_queries:
            unique_queries = [
                "What kind of documents were uploaded?",
                "Can you summarize the main topics?",
                "What are the most frequent keywords in these files?"
            ]

        import random
        random.shuffle(unique_queries)
        return unique_queries[:max_questions] if max_questions else unique_queries[:5]

    def evaluate(self, max_questions: int = 5) -> EvaluationReport:
        import nest_asyncio
        nest_asyncio.apply()
        
        start_time = time.time()
        run_id = str(uuid.uuid4())[:8]
        logger.info("starting_trulens_evaluation", run_id=run_id)

        queries = self._get_historical_queries(max_questions)
        
        from langchain_google_genai import ChatGoogleGenerativeAI
        from trulens.providers.langchain import Langchain

        gemini_llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=settings.gemini.gemini_api_key,
            temperature=0.0
        )
        provider = Langchain(llm=gemini_llm)

        context_scores = []
        faithfulness_scores = []
        answer_scores = []

        for q in queries:
            try:
                # 1. Generate using our pipeline
                resp = self.generator.generate(q, stream=False)
                if not resp or not resp.success:
                    continue
                
                # Format contexts
                contexts = "\n\n".join([c.content for c in resp.chunks_used])
                answer = resp.answer

                # 2. Score Context Relevance
                # Provider takes (question, statement)
                cr_score = provider.qs_relevance(q, contexts)
                context_scores.append(float(cr_score))

                # 3. Score Faithfulness (Groundedness)
                # Provider takes (source, statement)
                fs_score = provider.groundedness_measure_with_cot_reasons(contexts, answer)
                # Groundedness returns (score, explanation) tuple
                if isinstance(fs_score, tuple):
                    fs_score = fs_score[0]
                faithfulness_scores.append(float(fs_score))

                # 4. Score Answer Correctness (Relevance)
                # Provider takes (prompt, response)
                ar_score = provider.relevance(q, answer)
                answer_scores.append(float(ar_score))
                
            except Exception as e:
                logger.error("trulens_query_eval_failed", query=q, error=str(e))
                continue

        # Aggregate safely
        def avg(arr): return sum(arr) / len(arr) if arr else 0.0

        cr_avg = avg(context_scores)
        fs_avg = avg(faithfulness_scores)
        ar_avg = avg(answer_scores)

        # Check thresholds
        cr_pass = cr_avg >= self.thresholds["context_relevance"]
        fs_pass = fs_avg >= self.thresholds["faithfulness"]
        ar_pass = ar_avg >= self.thresholds["answer_correctness"]

        avg_score = (cr_avg + fs_avg + ar_avg) / 3.0
        overall_passed = cr_pass and fs_pass and ar_pass

        latency = (time.time() - start_time) * 1000

        report = EvaluationReport(
            run_id=run_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            dataset_size=len(queries),
            faithfulness=MetricResult(fs_avg, fs_pass, self.thresholds["faithfulness"]),
            context_relevance=MetricResult(cr_avg, cr_pass, self.thresholds["context_relevance"]),
            answer_correctness=MetricResult(ar_avg, ar_pass, self.thresholds["answer_correctness"]),
            overall_passed=overall_passed,
            avg_score=avg_score,
            evaluation_latency_ms=latency
        )

        self._save_report(report)
        return report

    def _save_report(self, report: EvaluationReport):
        reports_dir = Path("data/evaluation_reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"eval_{report.timestamp.replace(':', '')}.json"

        data = {
            "run_id": report.run_id,
            "timestamp": report.timestamp,
            "dataset_size": report.dataset_size,
            "overall_passed": report.overall_passed,
            "avg_score": report.avg_score,
            "evaluation_latency_ms": report.evaluation_latency_ms,
            "metrics": {
                "faithfulness": report.faithfulness._asdict(),
                "context_relevance": report.context_relevance._asdict(),
                "answer_correctness": report.answer_correctness._asdict(),
            }
        }
        
        import json
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        logger.info("trulens_report_saved", path=str(report_path), avg_score=report.avg_score)
