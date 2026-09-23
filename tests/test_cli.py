"""Tests para cli.py — helpers y comando info."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from yt_links_mp3.cli import _format_duration, _is_url_like, main

# ------------------- _is_url_like -------------------


def test_is_url_like_full_url() -> None:
    assert _is_url_like("https://www.youtube.com/watch?v=abc12345678") is True
    assert _is_url_like("http://youtu.be/abc12345678") is True


def test_is_url_like_bare_id() -> None:
    assert _is_url_like("dQw4w9WgXcQ") is True
    assert _is_url_like("abc-DEF_123") is True


def test_is_url_like_false_for_filepath() -> None:
    assert _is_url_like("links.txt") is False
    assert _is_url_like("./my_links.txt") is False
    assert _is_url_like("/tmp/links.txt") is False


def test_is_url_like_false_for_short_id() -> None:
    # 11 chars required; 10 o menos no es ID valido
    assert _is_url_like("dQw4w9WgXc") is False
    assert _is_url_like("short") is False


# ------------------- _format_duration -------------------


def test_format_duration_zero() -> None:
    assert _format_duration(0) == "?"
    assert _format_duration(None) == "?"


def test_format_duration_seconds_only() -> None:
    assert _format_duration(45) == "0:45"


def test_format_duration_minutes_and_seconds() -> None:
    assert _format_duration(125) == "2:05"
    assert _format_duration(599) == "9:59"


def test_format_duration_pads_seconds() -> None:
    assert _format_duration(62) == "1:02"
    assert _format_duration(605) == "10:05"


# ------------------- comando info (single URL) -------------------


def test_info_single_url_shows_metadata() -> None:
    """info con URL muestra metadata formateada."""
    fake_info = {
        "id": "dQw4w9WgXcQ",
        "title": "Never Gonna Give You Up",
        "uploader": "Rick Astley",
        "channel": "Rick Astley",
        "duration": 213,
    }
    runner = CliRunner()
    with patch("yt_links_mp3.downloader.fetch_metadata_cached", return_value=fake_info):
        result = runner.invoke(
            main,
            ["info", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        )
    assert result.exit_code == 0
    assert "Never Gonna Give You Up" in result.output
    assert "Rick Astley" in result.output
    assert "3:33" in result.output  # 213s = 3:33


def test_info_bare_id_works() -> None:
    """info acepta un ID solo de 11 chars."""
    fake_info = {
        "id": "dQw4w9WgXcQ",
        "title": "Test Song",
        "uploader": "Test Artist",
        "duration": 100,
    }
    runner = CliRunner()
    with patch("yt_links_mp3.downloader.fetch_metadata_cached", return_value=fake_info):
        result = runner.invoke(main, ["info", "dQw4w9WgXcQ"])
    assert result.exit_code == 0
    assert "Test Song" in result.output


def test_info_url_not_found_fails() -> None:
    """info con URL que falla muestra error y aborta."""
    runner = CliRunner()
    with patch(
        "yt_links_mp3.downloader.fetch_metadata_cached",
        side_effect=Exception("Video unavailable"),
    ):
        result = runner.invoke(main, ["info", "https://youtu.be/nonexistent1"])
    assert result.exit_code != 0


# ------------------- comando info (archivo) -------------------


def test_info_file_shows_table(tmp_path: Path) -> None:
    """info con archivo .txt muestra tabla con todos los links."""
    links_file = tmp_path / "links.txt"
    links_file.write_text("https://youtu.be/dQw4w9WgXcQ\nhttps://youtu.be/jNQXAC9IVRw\n")

    def fake_fetch(url, **_kwargs):
        return {
            "id": url.split("/")[-1],
            "title": f"Song {url[-11:]}",
            "uploader": "Some Artist",
            "duration": 200,
        }

    runner = CliRunner()
    with patch("yt_links_mp3.downloader.fetch_metadata_cached", side_effect=fake_fetch):
        result = runner.invoke(main, ["info", str(links_file)])
    assert result.exit_code == 0
    assert "Some Artist" in result.output
    assert "Song" in result.output


def test_info_file_not_found(tmp_path: Path) -> None:
    """info con archivo inexistente aborta con error."""
    runner = CliRunner()
    result = runner.invoke(main, ["info", str(tmp_path / "nope.txt")])
    assert result.exit_code != 0
    assert "no encontrado" in result.output.lower() or "nope" in result.output


def test_info_file_with_skipped_lines(tmp_path: Path) -> None:
    """info reporta líneas ignoradas si las hay."""
    links_file = tmp_path / "links.txt"
    links_file.write_text("# comentario\n\nhttps://youtu.be/dQw4w9WgXcQ\nno es un link\n")

    def fake_fetch(url, **_kwargs):
        return {"id": "abc", "title": "T", "uploader": "A", "duration": 100}

    runner = CliRunner()
    with patch("yt_links_mp3.downloader.fetch_metadata_cached", side_effect=fake_fetch):
        result = runner.invoke(main, ["info", str(links_file)])
    assert result.exit_code == 0
    # La línea inválida se reporta como skipped
    assert "ignoradas" in result.output.lower() or "1" in result.output


def test_info_file_one_link_fails_other_succeeds(tmp_path: Path) -> None:
    """Si una URL falla al fetch, las otras siguen y se reportan con error."""
    links_file = tmp_path / "links.txt"
    links_file.write_text("https://youtu.be/dQw4w9WgXcQ\nhttps://youtu.be/failvideoid\n")

    def fake_fetch(url, **_kwargs):
        if "fail" in url:
            raise Exception("Video unavailable")
        return {"id": "ok", "title": "OK Song", "uploader": "OK", "duration": 100}

    runner = CliRunner()
    with patch("yt_links_mp3.downloader.fetch_metadata_cached", side_effect=fake_fetch):
        result = runner.invoke(main, ["info", str(links_file)])
    assert result.exit_code == 0
    assert "OK Song" in result.output
    assert "err" in result.output.lower() or "fail" in result.output.lower()


# ============================================================
# SPEC-003: Info command polish (17 nuevos tests)
# ============================================================

# ---- Feature B: _format_duration maneja horas ----


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, "?"),
        (0, "?"),
        (59, "0:59"),
        (60, "1:00"),
        (213, "3:33"),
        (3599, "59:59"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
        (3930, "1:05:30"),
        (7325, "2:02:05"),
        (36000, "10:00:00"),
    ],
)
def test_format_duration_adaptive(seconds: int | float | None, expected: str) -> None:
    """Maneja horas >= 1h con H:MM:SS, y M:SS para < 1h. None/0 -> '?'."""
    assert _format_duration(seconds) == expected


def test_format_duration_truncates_float() -> None:
    """Floats se truncan a int antes de formatear."""
    assert _format_duration(213.7) == "3:33"
    assert _format_duration(3930.9) == "1:05:30"


# ---- Feature A: info <URL> muestra estado 'ya descargado' ----


def test_info_url_shows_downloaded_when_file_exists(tmp_path: Path) -> None:
    """info <URL> muestra '✓ Ya descargado' cuando _existing_path_for retorna un path."""
    fake_existing = tmp_path / "01 - Artist - Song.mp3"

    def fake_fetch(url: str, **_kwargs: object) -> dict:
        return {"id": "abc12345678", "title": "Song", "uploader": "Artist", "duration": 213}

    runner = CliRunner()
    with patch("yt_links_mp3.downloader.fetch_metadata_cached", side_effect=fake_fetch):
        with patch("yt_links_mp3.cli._existing_path_for", return_value=fake_existing):
            result = runner.invoke(main, ["info", "https://youtu.be/abc12345678"])
    assert result.exit_code == 0
    assert "Ya descargado" in result.output
    assert "01 - Artist - Song.mp3" in result.output


def test_info_url_shows_not_downloaded_when_file_missing(tmp_path: Path) -> None:
    """info <URL> muestra '— No descargado' cuando _existing_path_for retorna None."""

    def fake_fetch(url: str, **_kwargs: object) -> dict:
        return {"id": "abc12345678", "title": "Song", "uploader": "Artist", "duration": 213}

    runner = CliRunner()
    with patch("yt_links_mp3.downloader.fetch_metadata_cached", side_effect=fake_fetch):
        with patch("yt_links_mp3.cli._existing_path_for", return_value=None):
            result = runner.invoke(main, ["info", "https://youtu.be/abc12345678"])
    assert result.exit_code == 0
    assert "No descargado" in result.output


def test_info_bare_id_shows_downloaded_status(tmp_path: Path) -> None:
    """info <ID> (bare 11 chars) muestra el mismo estado que info <URL>."""
    fake_existing = tmp_path / "01 - Artist - Song.mp3"

    def fake_fetch(url: str, **_kwargs: object) -> dict:
        return {"id": "dQw4w9WgXcQ", "title": "Song", "uploader": "Artist", "duration": 213}

    runner = CliRunner()
    with patch("yt_links_mp3.downloader.fetch_metadata_cached", side_effect=fake_fetch):
        with patch("yt_links_mp3.cli._existing_path_for", return_value=fake_existing):
            result = runner.invoke(main, ["info", "dQw4w9WgXcQ"])
    assert result.exit_code == 0
    assert "Ya descargado" in result.output


# ---- Feature C: info <file> concurrente ----


def test_info_file_uses_concurrency(tmp_path: Path) -> None:
    """info <archivo> ejecuta fetch en paralelo (no secuencial) con ThreadPoolExecutor."""
    links = tmp_path / "links.txt"
    links.write_text("\n".join(f"https://youtu.be/dQw4w9Wg{i:02d}" for i in range(10)))

    current = 0
    max_concurrent = 0
    lock = threading.Lock()

    def fake_fetch(url: str, **_kwargs: object) -> dict:
        nonlocal current, max_concurrent
        with lock:
            current += 1
            max_concurrent = max(max_concurrent, current)
        time.sleep(0.1)
        with lock:
            current -= 1
        return {"id": "x", "title": "T", "uploader": "A", "duration": 100}

    runner = CliRunner()
    with patch("yt_links_mp3.downloader.fetch_metadata_cached", side_effect=fake_fetch):
        result = runner.invoke(main, ["info", str(links)])
    assert result.exit_code == 0
    assert max_concurrent >= 2, f"Esperaba concurrencia >= 2, max fue {max_concurrent}"


def test_info_file_preserves_order(tmp_path: Path) -> None:
    """info <archivo> preserva el orden de links.txt aunque fetches terminen fuera de orden."""
    links = tmp_path / "links.txt"
    ids = ["dQw4w9WgXcQ", "jNQXAC9IVRw", "9bZkp7q19f0", "kJQP7kiw5Fk", "4xDzrJKXOOY"]
    links.write_text("\n".join(f"https://youtu.be/{i}" for i in ids))

    def fake_fetch(url: str, **_kwargs: object) -> dict:
        video_id = url[-11:]
        idx = ids.index(video_id)
        # Latencia inversa: las primeras entradas demoran más, terminan últimas
        time.sleep((len(ids) - idx) * 0.02)
        return {"id": video_id, "title": f"Song-{idx}", "uploader": "Artist", "duration": 100}

    runner = CliRunner()
    with patch("yt_links_mp3.downloader.fetch_metadata_cached", side_effect=fake_fetch):
        result = runner.invoke(main, ["info", str(links)])
    assert result.exit_code == 0
    # Los títulos Song-0, Song-1, ... deben aparecer en el output en orden
    positions = [result.output.find(f"Song-{i}") for i in range(len(ids))]
    assert -1 not in positions, "Algún Song-{i} no apareció en output"
    assert positions == sorted(positions), f"Orden incorrecto: {positions}"
