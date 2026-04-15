import time
import uuid
import json
import re
from pathlib import Path
from typing import List, Dict, Any
from collections import namedtuple

from config.settings import get_settings
from config.logging_config import get_logger
from api.dependencies import get_answer_generator, get_metrics_tracker
from monitoring.feedback_store import FeedbackStore

from langchain_google_genai import ChatGoogleGenerativeAI

logger = get_logger(__name__)
settings = get_settings()

MetricResult = namedtuple("MetricResult", ["score", "passed", "threshold"])

COST_RATES = {
    "input": 0.0001 / 1000,
    "output": 0.0004 / 1000
}

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
        evaluation_latency_ms: float,
        total_cost_usd: float = 0.0,
        total_tokens: int = 0,
        questions: List[Dict[str, Any]] = None
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
        self.total_cost_usd = total_cost_usd
        self.total_tokens = total_tokens
        self.questions = questions or []

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "dataset_size": self.dataset_size,
            "overall_passed": self.overall_passed,
            "avg_score": round(self.avg_score, 4),
            "metrics": {
                "faithfulness": self.faithfulness._asdict(),
                "context_relevance": self.context_relevance._asdict(),
                "answer_correctness": self.answer_correctness._asdict()
            },
            "evaluation_latency_ms": round(self.evaluation_latency_ms, 2),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
            "questions": self.questions
        }

class TruLensEvaluator:
    def __init__(self):
        self.generator = get_answer_generator()
        self.feedback_store = FeedbackStore()
        self.metrics_tracker = get_metrics_tracker()
        self.thresholds = {
            "faithfulness": settings.evaluation.min_faithfulness_score,
            "context_relevance": settings.evaluation.min_context_relevance_score,
            "answer_correctness": settings.evaluation.min_answer_correctness_score
        }

    def _get_baseline_queries(self) -> List[Dict[str, str]]:
        """Return 3 static baseline questions for consistency."""
        return [
            {"query": "What are the main topics covered in the document?", "type": "baseline"},
            {"query": "List the key takeaways from the document?", "type": "baseline"},
            {"query": "What is the primary purpose of this document?", "type": "baseline"}
        ]

    def _generate_synthetic_queries(self, judge_llm) -> List[Dict[str, str]]:
        import random
        vector_store = self.generator.retriever.vector_store
        queries = []
        
        recent_chunks = vector_store.get_recent_chunks(limit=8)
        
        forbidden = [
            "summarize", "summary", "explain in detail", "describe in detail", 
            "elaborate", "analyze", "compare", "overview", "full explanation",
            "discuss", "provide details", "give details", "deep dive", 
            "comprehensive", "walk through", "step by step explanation"
        ]
        
        safe_fallbacks = [
            "What is the main purpose of the document?",
            "What key information is mentioned?",
            "What requirement is described in the document?",
            "What is discussed in the document?",
            "What important detail is mentioned?"
        ]

        def is_valid(q):
            q_lower = q.lower()
            if any(word in q_lower for word in forbidden): return False
            if len(q.split()) > 18: return False
            if " and " in q_lower or "?" in q[:-1]: return False
            return True

        if recent_chunks:
            ctx = "\n\n".join([c.content[:800] for c in recent_chunks[:6]])
            prompt = (
                f"Act as a meticulous user. Given the following snippets from a RECENTLY UPLOADED document, "
                f"generate 2 specific, short, factual questions. \n"
                f"RULES:\n"
                f"- Response must be FAST and CONCISE (answerable in 1-3 sentences).\n"
                f"- Avoid keywords: {', '.join(forbidden[:10])}...\n"
                f"- Avoid multi-part or comparative questions.\n\n"
                f"TEXT SNIPPETS:\n{ctx}\n\n"
                f"Return EXACTLY a JSON array of 2 strings. Example: [\"question 1\", \"question 2\"]"
            )
            try:
                res = judge_llm.invoke(prompt)
                text = res.content.strip()
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                
                q_list = json.loads(text)
                for q in q_list[:2]:
                    if is_valid(q):
                        queries.append({"query": q, "type": "recent"})
                    else:
                        queries.append({"query": random.choice(safe_fallbacks), "type": "recent_fallback"})
            except Exception as e:
                logger.warning("failed_to_generate_recent_queries", error=str(e))
                queries.append({"query": random.choice(safe_fallbacks), "type": "recent_fallback"})
        
        random_chunks = vector_store.get_random_chunks(limit=5)
        if random_chunks:
            ctx = "\n\n".join([c.content[:800] for c in random_chunks])
            prompt = (
                f"Act as a factual investigator. Given the following snippets from an knowledge base, "
                f"generate 1 short, factual definition or purpose-based question.\n"
                f"RULES:\n"
                f"- No summary/analysis/comparison.\n"
                f"- Must be answerable in 1-3 sentences.\n\n"
                f"TEXT SNIPPETS:\n{ctx}\n\n"
                f"Return EXACTLY a JSON array with 1 string. Example: [\"specific question\"]"
            )
            try:
                res = judge_llm.invoke(prompt)
                text = res.content.strip()
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                
                q_list = json.loads(text)
                if q_list and is_valid(q_list[0]):
                    queries.append({"query": q_list[0], "type": "random"})
                else:
                    queries.append({"query": random.choice(safe_fallbacks), "type": "random_fallback"})
            except Exception as e:
                logger.warning("failed_to_generate_random_queries", error=str(e))
                queries.append({"query": random.choice(safe_fallbacks), "type": "random_fallback"})
        
        return queries

    def _calculate_judge_cost(self, response) -> tuple[float, int]:
        """Extract tokens from LangChain response and calculate USD cost."""
        try:
            usage = getattr(response, 'usage_metadata', {})
            it = usage.get('prompt_tokens', 0)
            ot = usage.get('candidates_tokens', 0)
            tt = usage.get('total_tokens', 0)
            
            cost = (it * COST_RATES["input"]) + (ot * COST_RATES["output"])
            return cost, tt
        except Exception:
            return 0.0, 0

    def evaluate(self, max_questions: int = 6) -> EvaluationReport:
        run_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        logger.debug("starting_hybrid_native_evaluation", run_id=run_id)

        eval_model_name = settings.gemini.gemini_model
        judge_llm = ChatGoogleGenerativeAI(
            model=eval_model_name,
            google_api_key=settings.gemini.gemini_api_key,
            temperature=0.0
        )

        baselines = self._get_baseline_queries()
        synthetic = self._generate_synthetic_queries(judge_llm)
        all_eval_queries = baselines + synthetic
        
        logger.debug("hybrid_suite_generated", baselines=len(baselines), synthetic=len(synthetic))

        json_instr = "\n\nReturn EXACTLY a JSON object with a single key 'score' (float 0.0-1.0). Example: {\"score\": 0.8}"
        
        def parse_score(llm_output, metric_name):
            text = llm_output.content.strip()
            try:
                json_text = text
                if "```json" in text:
                    json_text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    json_text = text.split("```")[1].split("```")[0].strip()
                
                json_text = json_text.replace('\\"', '"')
                data = json.loads(json_text)
                
                score = None
                for k, v in data.items():
                    if 'score' in k.lower():
                        score = float(v)
                        break
                
                if score is not None:
                    return score
            except Exception:
                pass

            match = re.search(r'"score"\s*:\s*(\d?\.\d+)', text, re.IGNORECASE)
            if match: return float(match.group(1))

            match = re.search(r'score["\']?\s*:\s*(\d?\.\d+)', text, re.IGNORECASE)
            if match: return float(match.group(1))
            
            floats = re.findall(r'0\.\d+|1\.0', text)
            if floats: return float(floats[0])
            
            return 0.0

        context_scores = []
        faithfulness_scores = []
        answer_scores = []
        
        running_cost = 0.0
        running_tokens = 0
        executed_questions = []

        for item in all_eval_queries:
            q = item["query"]
            q_type = item["type"]
            try:
                logger.info(
                    "eval_progress", 
                    step = f"{all_eval_queries.index(item) + 1}/{len(all_eval_queries)}",
                    query = q[:80] + "..." if len(q) > 80 else q
                )
                
                resp = self.generator.generate(q, use_query_rewriting=False, use_multi_query=False)
                if not resp or not resp.success: continue
                
                running_cost += resp.cost_usd
                running_tokens += resp.total_tokens
                
                contexts = "\n\n".join([c.content[:1000] for c in resp.chunks_used])
                answer = resp.answer

                cr_p = f"Evaluate retrieval relevance (0-1). Context: {contexts}\n\nQuery: {q}{json_instr}"
                
                fs_p = (
                    f"Evaluate faithfulness (0-1). Does the answer reflect the provided context? "
                    f"IMPORTANT: If the answer states that information is missing or not found, AND the context indeed lacks the information, "
                    f"give it a 1.0 (faithfully honest).\n\n"
                    f"Context: {contexts}\n\nAnswer: {answer}{json_instr}"
                )
                
                ar_p = f"Evaluate answer correctness (0-1). Determine if the answer correctly fulfills the user query. Query: {q}\n\nAnswer: {answer}{json_instr}"

                cr_res = judge_llm.invoke(cr_p)
                c, t = self._calculate_judge_cost(cr_res)
                running_cost += c; running_tokens += t
                cr_score = parse_score(cr_res, "relevance")
                context_scores.append(cr_score)

                fs_res = judge_llm.invoke(fs_p)
                c, t = self._calculate_judge_cost(fs_res)
                running_cost += c; running_tokens += t
                fs_score = parse_score(fs_res, "faithfulness")
                faithfulness_scores.append(fs_score)

                ar_res = judge_llm.invoke(ar_p)
                c, t = self._calculate_judge_cost(ar_res)
                running_cost += c; running_tokens += t
                ar_score = parse_score(ar_res, "correctness")
                answer_scores.append(ar_score)

                executed_questions.append({
                    "query": q,
                    "type": q_type,
                    "answer": answer,
                    "scores": {
                        "relevance": cr_score, "faithfulness": fs_score, "correctness": ar_score
                    },
                    "judge_reasoning": {
                        "relevance": cr_res.content if hasattr(cr_res, 'content') else str(cr_res),
                        "faithfulness": fs_res.content if hasattr(fs_res, 'content') else str(fs_res),
                        "correctness": ar_res.content if hasattr(ar_res, 'content') else str(ar_res)
                    }
                })

                setattr(resp, "request_type", "evaluation")
                self.metrics_tracker.record(resp)
                
            except Exception as e:
                logger.error("eval_step_failed", query=q, error=str(e))
                continue

        def avg(arr): return sum(arr) / len(arr) if arr else 0.0

        cr_avg = avg(context_scores)
        fs_avg = avg(faithfulness_scores)
        ar_avg = avg(answer_scores)

        latency = (time.time() - start_time) * 1000

        report = EvaluationReport(
            run_id=run_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            dataset_size=len(executed_questions),
            faithfulness=MetricResult(fs_avg, fs_avg >= self.thresholds["faithfulness"], self.thresholds["faithfulness"]),
            context_relevance=MetricResult(cr_avg, cr_avg >= self.thresholds["context_relevance"], self.thresholds["context_relevance"]),
            answer_correctness=MetricResult(ar_avg, ar_avg >= self.thresholds["answer_correctness"], self.thresholds["answer_correctness"]),
            overall_passed=all([cr_avg >= self.thresholds["context_relevance"], fs_avg >= self.thresholds["faithfulness"], ar_avg >= self.thresholds["answer_correctness"]]),
            avg_score=(cr_avg + fs_avg + ar_avg) / 3.0,
            evaluation_latency_ms=latency,
            total_cost_usd=running_cost,
            total_tokens=running_tokens,
            questions=executed_questions
        )

        self._save_report(report)
        return report

    def _save_report(self, report: EvaluationReport):
        reports_dir = Path("data/evaluation_reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        safe_ts = report.timestamp.replace(':', '')
        report_path = reports_dir / f"eval_{safe_ts}.json"
        with open(report_path, "w") as f:
            json.dump(report.to_dict(), f, indent=4)
        logger.info("hybrid_report_saved", path=str(report_path), cost_usd=report.total_cost_usd)
