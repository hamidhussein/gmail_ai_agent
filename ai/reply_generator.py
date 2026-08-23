"""
GmailAI Assistant - Smart Reply Generator
"""
import logging
from typing import Optional, Dict, Any

from app.constants import ReplyTone
from app.config import config_manager
from ai.local_model import LocalOllamaClient
from ai.cloud_model import CloudOpenAIClient

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
        self.cloud_client = CloudOpenAIClient(
            default_model=config_manager.config.openai_model,
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
        """Generates email reply text using Hybrid AI with template fallback."""
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

        # Try Local AI first
        try:
            reply = self.local_client.generate_text(user_prompt, system_prompt)
            if reply and len(reply) > 20:
                return reply
        except Exception:
            pass

        # Try Cloud AI
        if self.cloud_client.is_configured():
            try:
                reply = self.cloud_client.generate_text(user_prompt, system_prompt)
                if reply and len(reply) > 20:
                    return reply
            except Exception:
                pass

        # High-quality template fallback if no AI is available
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
