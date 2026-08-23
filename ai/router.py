"""
GmailAI Assistant - Hybrid AI Router & Decision Engine
"""
import logging
from typing import Dict, Any, Tuple

from app.config import config_manager
from app.constants import AISource
from ai.local_model import LocalOllamaClient
from ai.cloud_model import CloudOpenAIClient
from ai.classifier import EmailClassifier, CLASSIFICATION_SYSTEM_PROMPT
from ai.confidence import ConfidenceEvaluator
from ai.schemas import EmailClassificationResult

logger = logging.getLogger("GmailAI.Router")


def _validate_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Passes a raw AI output dict through the EmailClassificationResult validator.
    Returns a sanitised dict safe for DB persistence.
    """
    try:
        result = EmailClassificationResult(**raw)
        return result.to_dict()
    except Exception as e:
        logger.warning(f"AI result validation failed ({e}), using safe defaults.")
        return EmailClassificationResult().to_dict()


class HybridAIRouter:
    """
    Intelligent Hybrid AI Router.
    Routes between Local Ollama, Cloud OpenAI, and Heuristics based on
    confidence threshold (default 85%). All results are validated through
    EmailClassificationResult before being returned to callers.
    """

    def __init__(self):
        self.local_client = LocalOllamaClient(
            base_url=config_manager.config.ollama_url,
            default_model=config_manager.config.ollama_model,
        )
        self.cloud_client = CloudOpenAIClient(
            default_model=config_manager.config.openai_model,
        )

    def classify_email(self, email_data: Dict[str, Any]) -> Tuple[Dict[str, Any], AISource]:
        """
        Executes hybrid classification workflow:
        1. Attempts Local AI (Ollama)
        2. Evaluates confidence. If >= 85%, accept local result.
        3. If < 85% or Ollama fails, routes to Cloud AI (OpenAI).
        4. If Cloud AI fails or is not configured, uses resilient Heuristic engine.

        All results are validated and clamped through EmailClassificationResult.
        """
        mode = config_manager.config.ai_mode.upper()
        confidence_threshold = config_manager.config.hybrid_confidence_threshold
        prompt = EmailClassifier.build_classification_prompt(email_data)

        # Mode: HEURISTIC only
        if mode == "HEURISTIC":
            res = EmailClassifier.classify_with_heuristics(email_data)
            return _validate_result(res), AISource.HEURISTIC_FALLBACK

        # Mode: CLOUD_ONLY
        if mode == "CLOUD_ONLY":
            if self.cloud_client.is_configured():
                try:
                    res = self.cloud_client.generate_json(prompt, CLASSIFICATION_SYSTEM_PROMPT)
                    if res:
                        res["confidence"] = ConfidenceEvaluator.evaluate(res)
                        return _validate_result(res), AISource.CLOUD_OPENAI
                except Exception as e:
                    logger.warning(f"Cloud-only AI failed, falling back to heuristics: {e}")
            res = EmailClassifier.classify_with_heuristics(email_data)
            return _validate_result(res), AISource.HEURISTIC_FALLBACK

        # Mode: LOCAL_ONLY
        if mode == "LOCAL_ONLY":
            try:
                res = self.local_client.generate_json(prompt, CLASSIFICATION_SYSTEM_PROMPT)
                if res:
                    res["confidence"] = ConfidenceEvaluator.evaluate(res)
                    return _validate_result(res), AISource.LOCAL_OLLAMA
            except Exception as e:
                logger.warning(f"Local-only AI failed, falling back to heuristics: {e}")
            res = EmailClassifier.classify_with_heuristics(email_data)
            return _validate_result(res), AISource.HEURISTIC_FALLBACK

        # Mode: HYBRID (Default & Recommended)
        # Step 1: Try Local AI first
        local_result = None
        try:
            local_result = self.local_client.generate_json(prompt, CLASSIFICATION_SYSTEM_PROMPT)
        except Exception as e:
            logger.debug(f"Local AI inference unavailable ({e}), routing to cloud/fallback...")

        if local_result:
            confidence = ConfidenceEvaluator.evaluate(local_result)
            local_result["confidence"] = confidence
            if confidence >= confidence_threshold:
                logger.info(f"Local AI decision accepted (Confidence: {confidence:.2f} >= {confidence_threshold})")
                return _validate_result(local_result), AISource.LOCAL_OLLAMA
            else:
                logger.info(f"Local AI confidence low ({confidence:.2f} < {confidence_threshold}), escalating to Cloud AI...")

        # Step 2: Escalate to Cloud AI
        if self.cloud_client.is_configured():
            try:
                cloud_result = self.cloud_client.generate_json(prompt, CLASSIFICATION_SYSTEM_PROMPT)
                if cloud_result:
                    cloud_result["confidence"] = ConfidenceEvaluator.evaluate(cloud_result)
                    logger.info("Cloud AI analysis completed.")
                    return _validate_result(cloud_result), AISource.CLOUD_OPENAI
            except Exception as e:
                logger.warning(f"Cloud AI analysis failed: {e}")

        # Step 3: Resilient Heuristic Fallback
        logger.info("Using Heuristic Rule Engine for email classification.")
        heuristic_result = EmailClassifier.classify_with_heuristics(email_data)
        return _validate_result(heuristic_result), AISource.HEURISTIC_FALLBACK


hybrid_router = HybridAIRouter()
