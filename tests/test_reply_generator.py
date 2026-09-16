"""Tests for reply generation routing, cleanup, and fallback behavior."""
from unittest.mock import MagicMock, patch

from ai.reply_generator import ReplyGenerator
from app.config import config_manager
from app.constants import ReplyTone


def _generate(generator: ReplyGenerator):
    return generator.generate_reply_with_source(
        sender_name="Sarah",
        sender_email="sarah@example.com",
        subject="Project timeline",
        original_body="Can you send the revised timeline by Friday?",
        tone=ReplyTone.PROFESSIONAL,
        user_name="Hamid",
    )


def test_local_only_uses_ollama_and_cleans_subject_header():
    generator = ReplyGenerator()
    generator.local_client = MagicMock()
    generator.local_client.generate_text.return_value = (
        "Subject: Re: Project timeline\n\nHi Sarah,\n\nI will send it Thursday.\n\nBest,\nHamid"
    )
    generator.gemini_client = MagicMock()
    generator.openai_client = MagicMock()

    with patch.object(config_manager.config, "ai_mode", "LOCAL_ONLY"):
        reply, source = _generate(generator)

    assert source == "Local Ollama"
    assert not reply.lower().startswith("subject:")
    assert "send it Thursday" in reply
    generator.gemini_client.generate_text.assert_not_called()
    generator.openai_client.generate_text.assert_not_called()


def test_cloud_only_does_not_call_local_model():
    generator = ReplyGenerator()
    generator.local_client = MagicMock()
    generator.gemini_client = MagicMock()
    generator.gemini_client.is_configured.return_value = True
    generator.gemini_client.generate_text.return_value = "Hi Sarah,\n\nI will send it Thursday.\n\nBest,\nHamid"
    generator.openai_client = MagicMock()

    with (
        patch.object(config_manager.config, "ai_mode", "CLOUD_ONLY"),
        patch.object(config_manager.config, "cloud_provider", "gemini"),
    ):
        reply, source = _generate(generator)

    assert source == "Google Gemini"
    assert "Thursday" in reply
    generator.local_client.generate_text.assert_not_called()


def test_heuristic_mode_returns_template_without_calling_models():
    generator = ReplyGenerator()
    generator.local_client = MagicMock()
    generator.gemini_client = MagicMock()
    generator.openai_client = MagicMock()

    with patch.object(config_manager.config, "ai_mode", "HEURISTIC"):
        reply, source = _generate(generator)

    assert source == "Template fallback"
    assert reply.startswith("Hi Sarah,")
    generator.local_client.generate_text.assert_not_called()
    generator.gemini_client.generate_text.assert_not_called()
    generator.openai_client.generate_text.assert_not_called()
