"""
GmailAI Assistant - Confidence & Uncertainty Evaluation
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("GmailAI.Confidence")


class ConfidenceEvaluator:
    """Evaluates classification confidence and decides routing thresholds."""

    @staticmethod
    def evaluate(raw_result: Optional[Dict[str, Any]]) -> float:
        """
        Extracts or calculates confidence score from classification results.
        Returns float between 0.0 and 1.0.
        """
        if not raw_result:
            return 0.0

        # Check direct score
        if "confidence" in raw_result:
            try:
                val = float(raw_result["confidence"])
                if val > 1.0:  # e.g., 95 -> 0.95
                    val = val / 100.0
                return max(0.0, min(1.0, val))
            except (ValueError, TypeError):
                pass

        # Calculate heuristic confidence based on field completeness
        required_fields = ["category", "importance_score", "reasoning", "suggested_action"]
        present = sum(1 for f in required_fields if raw_result.get(f) is not None)
        base_confidence = present / len(required_fields)

        # Boost confidence if reasoning is detailed
        reasoning = raw_result.get("reasoning", "")
        if len(reasoning) > 30:
            base_confidence = min(1.0, base_confidence + 0.1)

        return round(base_confidence, 2)
