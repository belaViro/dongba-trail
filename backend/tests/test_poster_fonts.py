"""SHARE-01: CJK font discovery across supported deployment environments."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.app import media
from backend.app.errors import ApiError

FONT_PATHS = (
    "C:/Windows/Fonts/msyh.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-droid/DroidSansFallback.ttf",
)


@pytest.mark.parametrize("font_path", FONT_PATHS)
@pytest.mark.parametrize("size", (24, 31, 76))
def test_chinese_font_uses_installed_cjk_font(monkeypatch, font_path, size):
    monkeypatch.setattr(Path, "is_file", lambda path: path == Path(font_path))
    loaded = object()
    loader = Mock(return_value=loaded)
    monkeypatch.setattr(media.ImageFont, "truetype", loader)
    assert media.chinese_font(size) is loaded
    loader.assert_called_once_with(str(Path(font_path)), size)


def test_chinese_font_preserves_existing_priority(monkeypatch):
    monkeypatch.setattr(Path, "is_file", lambda path: True)
    loader = Mock()
    monkeypatch.setattr(media.ImageFont, "truetype", loader)
    media.chinese_font(24)
    loader.assert_called_once_with(str(Path(FONT_PATHS[0])), 24)


def test_chinese_font_skips_unreadable_font(monkeypatch):
    monkeypatch.setattr(Path, "is_file", lambda path: True)
    loaded = object()
    loader = Mock(side_effect=[OSError("Synthetic unreadable font"), loaded])
    monkeypatch.setattr(media.ImageFont, "truetype", loader)
    assert media.chinese_font(31) is loaded
    assert loader.call_count == 2
    loader.assert_called_with(str(Path(FONT_PATHS[1])), 31)


@pytest.mark.parametrize("exists", (False, True))
def test_no_usable_font_remains_explicitly_unavailable(monkeypatch, exists):
    monkeypatch.setattr(Path, "is_file", lambda path: exists)
    loader = Mock(side_effect=OSError("Synthetic unreadable font"))
    monkeypatch.setattr(media.ImageFont, "truetype", loader)
    with pytest.raises(ApiError) as error:
        media.chinese_font(24)
    assert error.value.code == "POSTER_FONT_UNAVAILABLE"
    assert loader.call_count == (len(FONT_PATHS) if exists else 0)
