import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append('backend')

from evaluation.trulens_evaluator import TruLensEvaluator
from generation.answer_generator import AnswerGenerator
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import get_settings

settings = get_settings()

def test_single_eval():
    evaluator = TruLensEvaluator()
    judge_llm = ChatGoogleGenerativeAI(
        model=settings.gemini.gemini_model,
        google_api_key=settings.gemini.gemini_api_key,
        temperature=0.0
    )
    
    query = "What are the main topics covered in the document?"
    print(f"Testing Query: {query}")
    
    resp = evaluator.generator.generate(query, use_query_rewriting=False, use_multi_query=False)
    print(f"Generated Answer: {resp.answer[:200]}...")
    
    ar_p = f"Evaluate answer correctness (0-1). Query: {query}\n\nAnswer: {resp.answer}\n\nReturn EXACTLY a JSON object with a single key 'score' (float 0.0-1.0). Example: {{\"score\": 0.8}}"
    
    print("\nCalling Judge LLM for correctness...")
    res = judge_llm.invoke(ar_p)
    print(f"RAW JUDGE OUTPUT:\n{res.content}")
    
    # Try parsing
    score = 0.0
    text = res.content.strip()
    try:
        import json
        json_text = text
        if "```json" in text:
            json_text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            json_text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(json_text)
        score = data.get("score", 0.0)
    except:
        import re
        match = re.search(r'score["\']?\s*:\s*(\d?\.\d+)', text, re.IGNORECASE)
        if match: score = float(match.group(1))
        
    print(f"\nExtracted Score: {score}")

if __name__ == "__main__":
    test_single_eval()
