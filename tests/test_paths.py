"""Tests para paths.py — sanitización y construcción de filenames."""
from __future__ import annotations

from pathlib import Path

from yt_links_mp3.metadata import TrackMetadata
from yt_links_mp3.paths import (
    build_filename,
    ensure_unique_path,
    sanitize_component,
    sanitize_template,
)


# ------------------- sanitize_component -------------------


def test_sanitize_empty_returns_underscore() -> None:
    assert sanitize_component("") == "_"


def test_sanitize_replaces_forbidden_chars() -> None:
    assert sanitize_component('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"


def test_sanitize_strips_trailing_dots() -> None:
    assert sanitize_component("filename...") == "filename"


def test_sanitize_strips_whitespace() -> None:
    assert sanitize_component("  name  ") == "name"


def test_sanitize_windows_reserved() -> None:
    assert sanitize_component("CON") == "_CON"
    assert sanitize_component("PRN") == "_PRN"


def test_sanitize_caps_length() -> None:
    long = "a" * 300
    result = sanitize_component(long)
    assert len(result) == 200


# ------------------- sanitize_template -------------------


def test_template_simple_replacement() -> None:
    result = sanitize_template("{artist} - {title}", {"artist": "Artist", "title": "Song"})
    assert result == "Artist - Song"


def test_template_zero_padding() -> None:
    result = sanitize_template(
        "{track_number:02d} - {title}",
        {"track_number": 3, "title": "Song"},
    )
    assert result == "03 - Song"


def test_template_missing_key_returns_underscore() -> None:
    result = sanitize_template("{artist} - {missing}", {"artist": "A"})
    assert result == "A - _"


def test_template_sanitizes_segments() -> None:
    result = sanitize_template("{artist}/{title}", {"artist": "a/b", "title": "c?"})
    assert result == "a_b/c_"


# ------------------- build_filename -------------------


def test_build_filename_basic() -> None:
    m = TrackMetadata(artist="Artist", title="Song", track_number=1, video_id="abc")
    path = build_filename("{track_number:02d} - {artist} - {title}", m)
    assert path == Path("01 - Artist - Song.mp3")


def test_build_filename_default_template() -> None:
    m = TrackMetadata(artist="Rick Astley", title="Never Gonna Give You Up", track_number=5, video_id="abc")
    path = build_filename("{track_number:02d} - {artist} - {title}", m)
    assert path == Path("05 - Rick Astley - Never Gonna Give You Up.mp3")


def test_build_filename_sanitizes_forbidden_chars() -> None:
    m = TrackMetadata(artist="AC/DC", title="Song?", track_number=1, video_id="abc")
    path = build_filename("{track_number:02d} - {artist} - {title}", m)
    # / y ? se reemplazan por _
    assert path == Path("01 - AC_DC - Song_.mp3")


def test_build_filename_adds_ext_if_missing_in_template() -> None:
    m = TrackMetadata(artist="A", title="T", track_number=1, video_id="v")
    path = build_filename("{track_number:02d} - {artist} - {title}", m, ext="mp3")
    assert str(path).endswith(".mp3")


def test_build_filename_with_custom_ext() -> None:
    m = TrackMetadata(artist="A", title="T", track_number=1, video_id="v")
    path = build_filename("{track_number:02d} - {artist} - {title}.{ext}", m, ext="ogg")
    assert path == Path("01 - A - T.ogg")


# ------------------- ensure_unique_path -------------------


def test_ensure_unique_returns_same_when_not_exists(tmp_path: Path) -> None:
    target = tmp_path / "file.mp3"
    assert ensure_unique_path(target) == target


def test_ensure_unique_appends_counter(tmp_path: Path) -> None:
    (tmp_path / "file.mp3").touch()
    result = ensure_unique_path(tmp_path / "file.mp3")
    assert result == tmp_path / "file (1).mp3"


def test_ensure_unique_finds_next_free(tmp_path: Path) -> None:
    (tmp_path / "file.mp3").touch()
    (tmp_path / "file (1).mp3").touch()
    (tmp_path / "file (2).mp3").touch()
    result = ensure_unique_path(tmp_path / "file.mp3")
    assert result == tmp_path / "file (3).mp3"