import json
import uuid
import statistics
from pathlib import Path
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict

from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class UserFeedback:
    feedback_id: str 
    timestamp: str 
    date: str 

    query: str 
    answer: str 
    sources: List[dict] 

    rating: int 
    rating_label: str

    comment: Optional[str] = None 
    session_id: Optional[str] = None 

    rewritten_query: str = ""
    num_chunks_used: int = 0
    total_latency_ms: float = 0.0
    model_used: str = ""

@dataclass
class FeedbackSummary:
    period_days: int
    total_feedback: int
    positive: int 
    negative: int
    neutral: int
    positive_rate: float
    negative_rate: float
    avg_rating: float 
    recent_comments: List[str] 
    low_rated_queries: List[str]
    daily_trend: List[Dict[str, int]] = field(default_factory=list)

def _append_jsonl(file_path: Path, record: dict) -> None:
    file_path.parent.mkdir(parents = True, exist_ok = True)
    with open(file_path, "a", encoding = "utf-8") as f:
        f.write(json.dumps(record, ensure_ascii = False) + "\n")

def _read_jsonl(file_path: Path) -> List[dict]:
    if not file_path.exists():
        return []
    
    records = []
    with open(file_path, "r", encoding = "utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return records

class FeedbackStore:
    def __init__(self):
        self.feedback_dir = settings.feedback_log_path
        self.feedback_dir.mkdir(parents = True, exist_ok = True)

        logger.debug(
            "feedback_store_initialized",
            feedback_dir = str(self.feedback_dir)
        )
    
    def _today_file(self) -> Path:
        today = date.today().strftime("%Y_%m_%d")
        return self.feedback_dir / f"feedback_{today}.jsonl"

    def _load_recent_records(self, days: int = 30) -> List[dict]:
        all_records = []
        for offset in range(days):
            target = (
                date.today() - timedelta(days = offset)
            ).strftime("%Y_%m_%d")
            file_path = (
                self.feedback_dir / f"feedback_{target}.jsonl"
            )
            all_records.extend(_read_jsonl(file_path))
        return all_records
    
    def save(
        self,
        query: str,
        answer: str,
        rating: int,
        sources: List[dict]  = None,
        comment: Optional[str] = None,
        session_id: Optional[str] = None,
        rewritten_query: str = "",
        num_chunks_used: int = 0,
        total_latency_ms: float = 0.0,
        model_used: str = ""
    ) -> UserFeedback:
        if rating not in (1, 0, -1):
            logger.warning(
                "invalid_rating_clamping",
                raw_rating = rating
            )
            rating = max(-1, min(1, rating))

        rating_label = {
            1: "positive",
            0: "neutral",
            -1: "negative"
        }[rating]

        now = datetime.utcnow()
        feedback = UserFeedback(
            feedback_id = str(uuid.uuid4()),
            timestamp = now.isoformat() + "Z",
            date = now.strftime("%Y-%m-%d"),
            query = query,
            answer = answer,
            sources = sources or [],
            rating = rating,
            rating_label = rating_label,
            comment = comment,
            session_id = session_id,
            rewritten_query = rewritten_query,
            num_chunks_used = num_chunks_used,
            total_latency_ms = total_latency_ms,
            model_used = model_used
        )

        _append_jsonl(self._today_file(), asdict(feedback))

        logger.info(
            "feedback_saved",
            feedback_id = feedback.feedback_id,
            rating = rating_label,
            has_comment = comment is not None,
            query_preview = query[:80]
        )

        return feedback
    
    def get_negative_feedback(
        self,
        days: int = 30
    ) -> List[UserFeedback]:
        records = self._load_recent_records(days)

        negative = [
            UserFeedback(**r)
            for r in records
            if r.get("rating") == -1
        ]

        logger.debug(
            "negative_feedback_fetched",
            days = days,
            count = len(negative)
        )
        return negative
    
    def get_all_feedback(
        self,
        days: int = 30
    ) -> List[UserFeedback]:
        records = self._load_recent_records(days)
        return [UserFeedback(**r) for r in records]

    def get_summary(self, days: int = 30) -> FeedbackSummary:
        records = self._load_recent_records(days)

        if not records:
            return FeedbackSummary(
                period_days = days,
                total_feedback = 0,
                positive = 0,
                negative = 0,
                neutral = 0,
                positive_rate = 0.0,
                negative_rate = 0.0,
                avg_rating = 0.0,
                recent_comments = [],
                low_rated_queries = [],
                daily_trend = []
            )

        ratings = [r.get("rating", 0) for r in records]
        positive = sum(1 for r in ratings if r == 1)
        negative = sum(1 for r in ratings if r == -1)
        neutral = sum(1 for r in ratings if r == 0)
        total = len(records)

        negative_records = [
            r for r in records
            if r.get("rating") == -1 and r.get("comment")
        ]

        negative_records.sort(
            key = lambda x: x.get("timestamp", ""),
            reverse = True
        )
        recent_comments = [
            r["comment"]
            for r in negative_records[:10]
            if r.get("comment")
        ]

        low_rated_queries = list({
            r.get("query", "")[:100]
            for r in records
            if r.get("rating") == -1
        })[:20]

        from collections import defaultdict
        daily = defaultdict(lambda: {"date": "", "positive": 0, "negative": 0, "neutral": 0})
        for r in records:
            d = r.get("date", "")
            if not d: continue
            rt = r.get("rating", 0)
            daily[d]["date"] = d
            if rt == 1:
                daily[d]["positive"] += 1
            elif rt == -1:
                daily[d]["negative"] += 1
            else:
                daily[d]["neutral"] += 1
        
        daily_trend = sorted(list(daily.values()), key=lambda x: x["date"])

        return FeedbackSummary(
            period_days = days,
            total_feedback = total,
            positive = positive,
            negative = negative,
            neutral = neutral,
            positive_rate = round(positive / total, 3),
            negative_rate = round(negative / total, 3),
            avg_rating = round(statistics.mean(ratings), 3),
            recent_comments = recent_comments,
            low_rated_queries = low_rated_queries,
            daily_trend = daily_trend
        )
    
    