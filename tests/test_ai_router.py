"""
Unit Tests - Hybrid AI Router
"""
import pytest
from ai.router import HybridAIRouter
from ai.confidence import ConfidenceEvaluator
from app.constants import AISource


def test_confidence_evaluator():
    full_dict = {
        "category": "WORK",
        "importance_score": 85,
        "reasoning": "Team sprint sync discussion with direct action items assigned.",
        "suggested_action": "KEEP",
        "confidence": 0.95,
    }
    assert ConfidenceEvaluator.evaluate(full_dict) == 0.95

    missing_dict = {"category": "WORK"}
    score = ConfidenceEvaluator.evaluate(missing_dict)
    assert 0.0 < score < 0.85


def test_hybrid_router_fallback():
    router = HybridAIRouter()
    email_data = {
        "sender": "offers@sales-deal.com",
        "subject": "50% Discount on cloud compute",
        "body_plain": "Limited time promo coupon code SAVE50.",
    }
    # Should resolve cleanly via fallback heuristic or available model
    result, source = router.classify_email(email_data)
    assert result["category"] in ["PROMOTION", "ADVERTISEMENT"]
    assert result["suggested_action"] == "ARCHIVE"
    assert source in [AISource.HEURISTIC_FALLBACK, AISource.LOCAL_OLLAMA, AISource.CLOUD_OPENAI]
