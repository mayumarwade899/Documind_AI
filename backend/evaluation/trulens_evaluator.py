import time
import uuid
import json
import re
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Any
from collections import namedtuple

from config.settings import get_settings
from config.logging_config import get_logger

from generation.answer_generator import AnswerGenerator
from generation.llm_client import GeminiClient
from monitoring.metrics_tracker import MetricsTracker

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
        self.thresholds = {
            "faithfulness": settings.evaluation.min_faithfulness_score,
            "context_relevance": settings.evaluation.min_context_relevance_score,
            "answer_correctness": settings.evaluation.min_answer_correctness_score
        }



    def _generate_synthetic_queries(self, judge_llm) -> List[Dict[str, str]]:
        import random
        temp_generator = AnswerGenerator()
        vector_store = temp_generator.retriever.vector_store
        
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

        perspectives = ["a skeptical researcher", "a curious student", "a technical auditor", "a precise lawyer"]
        jitter = random.choice(perspectives)

        if recent_chunks:
            ctx = "\n\n".join([c.content[:800] for c in recent_chunks[:6]])
            prompt = (
                f"Act as {jitter}. Given the snippets from a document, generate 6 specific, very short, factual questions. \n"
                f"RULES:\n"
                f"- FOCUS on unique entities, specific clauses, or rare technical terms.\n"
                f"- ENSURE the answer to your question is explicitly present in the snippets PROVIDED.\n"
                f"- If a snippet mentions a professional term but doesn't define it, DO NOT ask for that definition.\n"
                f"- DO NOT ask summary-style questions (e.g., 'What are the main topics?', 'Summarize this document').\n"
                f"- Response must be FAST and CONCISE.\n"
                f"- Avoid keywords: {', '.join(forbidden[:10])}...\n\n"
                f"TEXT SNIPPETS:\n{ctx}\n\n"
                f"Return EXACTLY a JSON array of 6 strings."
            )
            try:
                res = judge_llm.invoke(prompt)
                text = res.content.strip()
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                
                q_list = json.loads(text)
                for q in q_list[:6]:
                    if is_valid(q):
                        queries.append({"query": q, "type": "recent"})
                    else:
                        queries.append({"query": random.choice(safe_fallbacks), "type": "recent_fallback"})
            except Exception as e:
                logger.warning("failed_to_generate_recent_queries", error=str(e))
                queries.append({"query": random.choice(safe_fallbacks), "type": "recent_fallback"})
        
        # Backfill if we undershoot. We want exactly 6 synthetic questions.
        target_synthetic = 6
        if len(queries) < target_synthetic:
            logger.info("synthetic_backfill_triggered", current=len(queries), target=target_synthetic)
            
        while len(queries) < target_synthetic:
            random_chunks = vector_store.get_random_chunks(limit=5)
            # If we literally have no data, fallback to extra baselines
            if not random_chunks:
                logger.warning("vector_store_empty_during_backfill")
                extra_baselines = [
                    "What are the specific requirements mentioned?",
                    "Are there any limitations discussed in the text?",
                    "What are the key definitions provided?"
                ]
                while len(queries) < target_synthetic:
                    queries.append({"query": extra_baselines.pop(0), "type": "synthetic_fallback"})
                break
            
            ctx = "\n\n".join([c.content[:800] for c in random_chunks])
            prompt = (
                f"Act as {jitter}. Given the snippets, generate 1 short factual question.\n"
                f"RULES:\n"
                f"- Response must be FAST and CONCISE.\n"
                f"TEXT SNIPPETS:\n{ctx}\n\n"
                f"Return EXACTLY a JSON array with 1 string. Example: [\"question\"]"
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

    def _evaluate_single(self, query_item: Dict[str, str]) -> Dict[str, Any]:
        """
        Processes a single query item in a thread-safe manner.
        Instantiates local generator/tracker to avoid race conditions.
        """
        q = query_item["query"]
        q_type = query_item["type"]
        
        local_generator = AnswerGenerator()
        local_tracker = MetricsTracker()
        
        try:
            local_generator = AnswerGenerator()
            local_tracker = MetricsTracker()
            
            local_judge = ChatGoogleGenerativeAI(
                model=settings.gemini.gemini_model,
                google_api_key=settings.gemini.gemini_api_key,
                temperature=0.0
            )

            # Increase retrieval depth (top_k=8) to ensure summary questions have enough context
            resp = local_generator.generate(q, use_query_rewriting=False, use_multi_query=False, top_k=8)
            if not resp or not resp.success:
                return {"error": "rag_failed", "query": q}
            
            contexts = "\n\n".join([c.content[:1000] for c in resp.chunks_used])
            answer = resp.answer

            trinity_prompt = (
                f"You are a meticulous RAG auditor. Evaluate the following RAG completion against the context.\n\n"
                f"CONTEXT (XML BOUNDED):\n<context>\n{contexts}\n</context>\n\n"
                f"QUERY: {q}\n\n"
                f"ANSWER: {answer}\n\n"
                f"STRICT SCORING RULES:\n"
                f"1. FAITHFULNESS (0.0 to 1.0):\n"
                f"   - EVERY claim must be inside the <context> tags.\n"
                f"   - EVERY claim must have a [Snippet X] citation in the answer.\n"
                f"   - DEDUCT 0.2 points for every claim without a citation.\n"
                f"   - DEDUCT 0.5 points for any claim that uses external legal knowledge (e.g. naming an Act not in context).\n"
                f"2. RELEVANCE (0.0 to 1.0): Is the context actually helpful?\n"
                f"3. CORRECTNESS (0.0 to 1.0): Does it answer the query accurately based ONLY on context?\n\n"
                f"Return EXACTLY a JSON object:\n"
                f"{{\n"
                f"  \"relevance\": {{\"score\": float, \"reason\": \"string\"}},\n"
                f"  \"faithfulness\": {{\"score\": float, \"reason\": \"string\"}},\n"
                f"  \"correctness\": {{\"score\": float, \"reason\": \"string\"}}\n"
                f"}}"
            )

            # 3. Judge Interaction with Retry Logic
            scores_data = None
            max_retries = 2
            
            for attempt in range(max_retries):
                try:
                    judge_res = local_judge.invoke(trinity_prompt)
                    j_cost, j_tokens = self._calculate_judge_cost(judge_res)
                    
                    text = judge_res.content.strip()
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0].strip()
                    
                    scores_data = json.loads(text)
                    break # Success
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error("grading_failed_after_retries", query=q, error=str(e))
                        return {"error": "grading_failed", "query": q}
                    logger.warning("grading_retry_triggered", query=q, attempt=attempt+1)

            # Record metrics
            setattr(resp, "request_type", "evaluation")
            local_tracker.record(resp)

            return {
                "query": q,
                "type": q_type,
                "answer": answer,
                "cost": resp.cost_usd + j_cost,
                "tokens": resp.total_tokens + j_tokens,
                "metrics": {
                    "relevance": scores_data.get("relevance", {}).get("score", 0.0),
                    "faithfulness": scores_data.get("faithfulness", {}).get("score", 0.0),
                    "correctness": scores_data.get("correctness", {}).get("score", 0.0)
                },
                "reasoning": {
                    "relevance": scores_data.get("relevance", {}).get("reason", ""),
                    "faithfulness": scores_data.get("faithfulness", {}).get("reason", ""),
                    "correctness": scores_data.get("correctness", {}).get("reason", "")
                }
            }

        except Exception as e:
            logger.error("evaluate_single_failed", query=q, error=str(e))
            return {"error": str(e), "query": q}

    def evaluate(self, max_questions: int = 6) -> EvaluationReport:
        run_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        logger.info("starting_optimized_dynamic_evaluation", run_id=run_id, max_workers=settings.evaluation.evaluation_max_workers)

        discovery_judge = ChatGoogleGenerativeAI(
            model=settings.gemini.gemini_model,
            google_api_key=settings.gemini.gemini_api_key,
            temperature=0.7
        )

        # We use only automatically generated smart questions (synthetic) to ensure alignment with doc content
        synthetic = self._generate_synthetic_queries(discovery_judge)
        all_eval_queries = synthetic[:max_questions]
        
        executed_results = []
        max_workers = settings.evaluation.evaluation_max_workers
        timeout = settings.evaluation.evaluation_timeout

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_query = {
                executor.submit(self._evaluate_single, query_item): query_item 
                for query_item in all_eval_queries
            }
            
            for future in concurrent.futures.as_completed(future_to_query):
                query_item = future_to_query[future]
                try:
                    result = future.result(timeout=timeout)
                    if "error" not in result:
                        executed_results.append(result)
                    else:
                        logger.warning("evaluation_item_failed", query=query_item["query"], error=result["error"])
                except Exception as e:
                    logger.error("evaluation_future_failed", query=query_item["query"], error=str(e))

        total_cost = sum(r["cost"] for r in executed_results)
        total_tokens = sum(r["tokens"] for r in executed_results)
        
        rel_scores = [r["metrics"]["relevance"] for r in executed_results]
        faith_scores = [r["metrics"]["faithfulness"] for r in executed_results]
        corr_scores = [r["metrics"]["correctness"] for r in executed_results]
        
        def avg(arr): return sum(arr) / len(arr) if arr else 0.0
        
        rel_avg = avg(rel_scores)
        faith_avg = avg(faith_scores)
        corr_avg = avg(corr_scores)

        questions_report = []
        for r in executed_results:
            questions_report.append({
                "query": r["query"],
                "type": r["type"],
                "answer": r["answer"],
                "scores": r["metrics"],
                "judge_reasoning": r["reasoning"]
            })

        latency = (time.time() - start_time) * 1000

        report = EvaluationReport(
            run_id=run_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            dataset_size=len(executed_results),
            faithfulness=MetricResult(faith_avg, faith_avg >= self.thresholds["faithfulness"], self.thresholds["faithfulness"]),
            context_relevance=MetricResult(rel_avg, rel_avg >= self.thresholds["context_relevance"], self.thresholds["context_relevance"]),
            answer_correctness=MetricResult(corr_avg, corr_avg >= self.thresholds["answer_correctness"], self.thresholds["answer_correctness"]),
            overall_passed=all([
                rel_avg >= self.thresholds["context_relevance"],
                faith_avg >= self.thresholds["faithfulness"],
                corr_avg >= self.thresholds["answer_correctness"]
            ]),
            avg_score=(rel_avg + faith_avg + corr_avg) / 3.0,
            evaluation_latency_ms=latency,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            questions=questions_report
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
        logger.info("evaluation_report_saved", path=str(report_path), questions=report.dataset_size, total_time_s=report.evaluation_latency_ms/1000)
