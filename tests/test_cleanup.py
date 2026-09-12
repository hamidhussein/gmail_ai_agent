"""Smart Cleanup safety and routing tests."""
from app.constants import ActionType
from ui.review_screen import ReviewScreenView


def test_cleanup_only_executes_archive_or_trash_actions():
    assert ReviewScreenView._is_supported_action(ActionType.ARCHIVE)
    assert ReviewScreenView._is_supported_action(ActionType.MOVE_TRASH)
    assert ReviewScreenView._is_supported_action("UNSUBSCRIBE_AND_TRASH")
    assert not ReviewScreenView._is_supported_action(ActionType.LABEL)
    assert not ReviewScreenView._is_supported_action(ActionType.STAR)


def test_cleanup_action_normalization_supports_enum_and_string_values():
    assert ReviewScreenView._action_value(ActionType.ARCHIVE) == "ARCHIVE"
    assert ReviewScreenView._action_value("archive") == "ARCHIVE"
