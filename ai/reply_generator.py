"""
GmailAI Assistant - Smart Reply Generator
"""
import logging
import re
from typing import Optional, Tuple

from app.constants import ReplyTone
from app.config import config_manager
from ai.local_model import LocalOllamaClient
from ai.cloud_model import CloudOpenAIClient
from ai.gemini_model import CloudGeminiClient

logger = logging.getLogger("GmailAI.ReplyGenerator")

TONE_PROMPT_INSTRUCTIONS = {
    ReplyTone.PROFESSIONAL: "Write in a polished, respectful, clear, and business-professional tone.",
    ReplyTone.FRIENDLY: "Write in a warm, polite, approachable, and friendly tone.",
    ReplyTone.SHORT: "Write a direct, concise response in 2-3 sentences max. Get straight to the point.",
    ReplyTone.DETAILED: "Write a comprehensive, step-by-step, thorough response covering all aspects mentioned.",
    ReplyTone.APOLOGY: "Write an understanding, polite apology acknowledging any delay or issue, and propose a solution.",
    ReplyTone.FOLLOW_UP: "Write a proactive check-in following up on next steps or previous milestones.",
}


class ReplyGenerator:
    """Generates context-aware draft replies tailored to user tone and custom instructions."""

    def __init__(self):
        self.local_client = LocalOllamaClient(
            base_url=config_manager.config.ollama_url,
            default_model=config_manager.config.ollama_model,
        )
        self.openai_client = CloudOpenAIClient(
            default_model=config_manager.config.openai_model,
        )
        self.gemini_client = CloudGeminiClient(
            default_model=config_manager.config.gemini_model,
        )

    def generate_reply(
        self,
        sender_name: str,
        sender_email: str,
        subject: str,
        original_body: str,
        tone: ReplyTone = ReplyTone.PROFESSIONAL,
        user_name: str = "Alex",
        extra_instructions: Optional[str] = None,
    ) -> str:
        """Generate a reply while preserving the original string-only API."""
        reply, _source = self.generate_reply_with_source(
            sender_name=sender_name,
            sender_email=sender_email,
            subject=subject,
            original_body=original_body,
            tone=tone,
            user_name=user_name,
            extra_instructions=extra_instructions,
        )
        return reply

    def generate_reply_with_source(
        self,
        sender_name: str,
        sender_email: str,
        subject: str,
        original_body: str,
        tone: ReplyTone = ReplyTone.PROFESSIONAL,
        user_name: str = "Alex",
        extra_instructions: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generate a reply using the configured routing mode and report its source."""
        tone_instruction = TONE_PROMPT_INSTRUCTIONS.get(tone, TONE_PROMPT_INSTRUCTIONS[ReplyTone.PROFESSIONAL])
        
        system_prompt = f"""You are an elite executive email assistant drafting a reply for {user_name}.
Tone style: {tone.value} - {tone_instruction}
Rules:
1. Output ONLY the email body text. Do NOT include placeholder headers like 'Subject:' or markdown formatting.
2. Sign off with the user's name: '{user_name}'.
3. Keep the reply relevant, actionable, and courteous.
"""

        user_prompt = f"""Incoming Email:
From: {sender_name} <{sender_email}>
Subject: {subject}
Content:
{original_body[:3000]}

User specific notes/instructions: {extra_instructions or 'None'}

Draft the reply:"""

        mode = config_manager.config.ai_mode.upper()

        if mode in {"HYBRID", "LOCAL_ONLY"}:
            try:
                reply = self._clean_reply(self.local_client.generate_text(user_prompt, system_prompt))
                if reply:
                    return reply, "Local Ollama"
            except Exception as ex:
                logger.info("Local reply generation unavailable: %s", ex)

        cloud_clients = []
        provider = config_manager.config.cloud_provider.lower()
        if provider == "gemini":
            cloud_clients = [(self.gemini_client, "Google Gemini"), (self.openai_client, "OpenAI")]
        else:
            cloud_clients = [(self.openai_client, "OpenAI"), (self.gemini_client, "Google Gemini")]

        if mode in {"HYBRID", "CLOUD_ONLY"}:
            for client, source in cloud_clients:
                if client.is_configured():
                    try:
                        reply = self._clean_reply(client.generate_text(user_prompt, system_prompt))
                        if reply:
                            return reply, source
                    except Exception as ex:
                        logger.info("%s reply generation unavailable: %s", source, ex)

        return self._template_reply(sender_name, subject, tone, user_name), "Template fallback"

    @staticmethod
    def _clean_reply(reply: Optional[str]) -> str:
        """Normalize model output and reject empty or unusably short replies."""
        cleaned = (reply or "").strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:text|markdown)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        lines = cleaned.splitlines()
        if lines and lines[0].strip().lower().startswith("subject:"):
            lines = lines[1:]
            while lines and not lines[0].strip():
                lines.pop(0)
            cleaned = "\n".join(lines).strip()
        return cleaned if len(cleaned) > 20 else ""

    @staticmethod
    def _template_reply(sender_name: str, subject: str, tone: ReplyTone, user_name: str) -> str:
        """Return a safe deterministic reply when configured AI engines are unavailable."""
        salutation = f"Hi {sender_name.split()[0] if sender_name else 'there'},"
        if tone == ReplyTone.SHORT:
            return f"{salutation}\n\nThank you for your email. I have received your message regarding '{subject}' and will review it shortly.\n\nBest regards,\n{user_name}"
        elif tone == ReplyTone.FRIENDLY:
            return f"{salutation}\n\nThanks so much for reaching out! I appreciate the update regarding '{subject}'. I'll take a look at the details and get back to you soon.\n\nHave a great day!\n{user_name}"
        elif tone == ReplyTone.FOLLOW_UP:
            return f"{salutation}\n\nI wanted to follow up regarding our discussion on '{subject}'. Please let me know if you need any additional information from my side to keep things moving forward.\n\nBest regards,\n{user_name}"
        elif tone == ReplyTone.APOLOGY:
            return f"{salutation}\n\nApologies for the delay in getting back to you regarding '{subject}'. Thank you for your patience while I reviewed this. I am now working on the next steps.\n\nSincerely,\n{user_name}"
        else:
            return f"{salutation}\n\nThank you for reaching out regarding '{subject}'. I have reviewed your notes and am coordinating the necessary next steps. I will keep you posted with any updates.\n\nBest regards,\n{user_name}"


reply_generator = ReplyGenerator()
