"""
Unit Tests - Hybrid AI Router
"""
import pytest
from unittest.mock import patch

from ai.router import HybridAIRouter
from ai.confidence import ConfidenceEvaluator
from app.config import config_manager
from app.constants import AISource
from core.exceptions import CloudModelError, LocalModelUnavailableError


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
    with (
        patch.object(config_manager.config, "ai_mode", "HYBRID"),
        patch.object(
            router.local_client,
            "generate_json",
            side_effect=LocalModelUnavailableError("offline"),
        ),
        patch.object(router.gemini_client, "is_configured", return_value=False),
        patch.object(router.openai_client, "is_configured", return_value=False),
    ):
        result, source = router.classify_email(email_data)

    assert result["category"] in ["PROMOTION", "ADVERTISEMENT"]
    assert result["suggested_action"] == "ARCHIVE"
    assert source == AISource.HEURISTIC_FALLBACK


def test_hybrid_router_circuit_breakers_skip_repeated_provider_failures():
    router = HybridAIRouter()
    email_data = {
        "sender": "offers@sales-deal.com",
        "subject": "50% Discount on cloud compute",
        "body_plain": "Limited time promo coupon code SAVE50.",
    }

    with (
        patch.object(config_manager.config, "ai_mode", "HYBRID"),
        patch.object(config_manager.config, "cloud_provider", "gemini"),
        patch.object(
            router.local_client,
            "generate_json",
            side_effect=LocalModelUnavailableError("timed out"),
        ) as local_generate,
        patch.object(router.gemini_client, "is_configured", return_value=True),
        patch.object(
            router.gemini_client,
            "generate_json",
            side_effect=CloudModelError("429 RESOURCE_EXHAUSTED"),
        ) as cloud_generate,
    ):
        first_result, first_source = router.classify_email(email_data)
        second_result, second_source = router.classify_email(email_data)

    assert first_source == AISource.HEURISTIC_FALLBACK
    assert second_source == AISource.HEURISTIC_FALLBACK
    assert first_result["category"] == second_result["category"]
    assert local_generate.call_count == 1
    assert cloud_generate.call_count == 1
