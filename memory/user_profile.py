"""
GmailAI Assistant - User Profile & Identity
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.config import config_manager
from app.constants import ReplyTone

logger = logging.getLogger("GmailAI.UserProfile")


class UserProfileModel(BaseModel):
    """Represents local user profile, writing tone, and personalization."""
    name: str = "User"
    primary_email: str = ""
    company_name: Optional[str] = None
    default_reply_tone: str = ReplyTone.PROFESSIONAL.value
    signature: str = "Best regards,\n[Name]"
    vip_domains: list[str] = Field(default_factory=list)


class UserProfileManager:
    """Manages reading and writing user profile state to disk."""

    def __init__(self):
        self.profile_path = config_manager.base_dir / "user_profile.json"
        self._profile = self.load()

    @property
    def profile(self) -> UserProfileModel:
        return self._profile

    def load(self) -> UserProfileModel:
        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return UserProfileModel(**data)
            except Exception as e:
                logger.warning(f"Failed to load user profile: {e}")
        return UserProfileModel()

    def save(self) -> None:
        try:
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self._profile.model_dump(), f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save user profile: {e}")

    def update_profile(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self._profile, k):
                setattr(self._profile, k, v)
        self.save()


user_profile_manager = UserProfileManager()
