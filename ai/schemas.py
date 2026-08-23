"""
GmailAI Assistant - AI Output Validation Schemas

All AI model responses are validated through these Pydantic models before
being persisted to the database. This prevents hallucinated or out-of-range
values from corrupting email records.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.constants import EmailCategory, ActionType, RiskLevel


# Valid enum string values for fast membership checks
_VALID_CATEGORIES = {e.value for e in EmailCategory}
_VALID_ACTIONS = {e.value for e in ActionType}
_VALID_RISK_LEVELS = {e.value for e in RiskLevel}


class EmailClassificationResult(BaseModel):
    """
    Validated, clamped output from any AI classification source
    (Local Ollama, Cloud OpenAI, or Heuristic engine).

    All fields are validated and clamped so that no AI hallucination
    can persist invalid data to the database.
    """
    category: str = Field(default=EmailCategory.PERSONAL.value)
    importance_score: int = Field(default=50, ge=0, le=100)
    urgency_score: int = Field(default=50, ge=0, le=100)
    risk_level: str = Field(default=RiskLevel.LOW.value)
    suggested_action: str = Field(default=ActionType.KEEP.value)
    confidence: float = Field(default=0.70, ge=0.0, le=1.0)
    reasoning: str = Field(default="")
    action_items: List[str] = Field(default_factory=list)

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v: str) -> str:
        val = str(v).strip().upper()
        if val in _VALID_CATEGORIES:
            return val
        return EmailCategory.PERSONAL.value

    @field_validator("risk_level", mode="before")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        val = str(v).strip().upper()
        if val in _VALID_RISK_LEVELS:
            return val
        return RiskLevel.LOW.value

    @field_validator("suggested_action", mode="before")
    @classmethod
    def validate_suggested_action(cls, v: str) -> str:
        val = str(v).strip().upper()
        if val in _VALID_ACTIONS:
            return val
        return ActionType.KEEP.value

    @field_validator("importance_score", "urgency_score", mode="before")
    @classmethod
    def clamp_score(cls, v) -> int:
        try:
            return max(0, min(100, int(float(v))))
        except (TypeError, ValueError):
            return 50

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.70

    @field_validator("action_items", mode="before")
    @classmethod
    def ensure_string_list(cls, v) -> List[str]:
        if not isinstance(v, list):
            return []
        return [str(item) for item in v if item]

    @field_validator("reasoning", mode="before")
    @classmethod
    def ensure_string(cls, v) -> str:
        return str(v) if v else ""

    def to_dict(self) -> dict:
        """Converts to a plain dict compatible with the email_data schema."""
        return {
            "category": self.category,
            "importance_score": self.importance_score,
            "urgency_score": self.urgency_score,
            "risk_level": self.risk_level,
            "suggested_action": self.suggested_action,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "action_items": self.action_items,
        }
