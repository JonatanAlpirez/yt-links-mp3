"""Tests para downloader.py — retry, concurrencia y edge cases.

Mockeamos yt_dlp.YoutubeDL y _try_download para no hacer requests reales.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from yt_dlp.utils import DownloadError, ExtractorError, UnavailableVideoError

from yt_links_mp3.config import Config
from yt_links_mp3.downloader import (
    _is_transient_error,
    download_all,
    download_one,
    write_failed_links,
)
from yt_links_mp3.linklist import LinkEntry


# ------------------- Helpers -------------------


def _make_config(tmp_path: Path, **overrides) -> Config:
    """Crea un Config con output_dir temporal y overrides."""
    defaults = {
        "output_dir": tmp_path,
        "audio_format": "mp3",
        "audio_quality": 192,
        "concurrency": 1,
        "max_retries": 3,
        "retry_backoff_base": 0.0,  # Sin sleep en tests
        "force": False,
        "dry_run": False,
        "embed_thumbnail": False,
        "filename_template": "{track_number:02d} - {artist} - {title}.{ext}",
    }
    defaults.update(overrides)
    return Config(**defaults)


def _make_entry(video_id: str = "dQw4w9WgXcQ", description: str | None = None) -> LinkEntry:
    return LinkEntry(
        video_id=video_id,
        url=f"https://youtu.be/{video_id}",
        description=description,
        line_number=1,
        raw=f"https://youtu.be/{video_id}",
    )


def _make_info(video_id: str = "dQw4w9WgXcQ") -> dict:
    """Simula la respuesta de yt-dlp extract_info."""
    return {
        "id": video_id,
        "title": "Test Song",
        "uploader": "Test Artist",
        "duration": 200,
        "thumbnails": [],
    }


# ------------------- _is_transient_error -------------------


def test_transient_generic_exception() -> None:
    """Errores genéricos se tratan como transitorios (reintentar)."""
    assert _is_transient_error(Exception("connection reset")) is True
    assert _is_transient_error(TimeoutError("timed out")) is True


def test_transient_network_message() -> None:
    """Mensajes de error de red son transitorios."""
    assert _is_transient_error(DownloadError("HTTP Error 503: Service Unavailable")) is True
    assert _is_transient_error(DownloadError("Connection timed out")) is True


def test_permanent_unavailable_video() -> None:
    """UnavailableVideoError es permanente."""
    assert _is_transient_error(UnavailableVideoError("video unavailable")) is False


def test_permanent_private_video_message() -> None:
    """Mensaje 'private video' es permanente."""
    assert _is_transient_error(DownloadError("private video")) is False
    assert _is_transient_error(DownloadError("Video is private")) is False


def test_permanent_404_message() -> None:
    """Mensaje '404' es permanente."""
    assert _is_transient_error(DownloadError("HTTP Error 404: Not Found")) is False


def test_permanent_age_restricted_message() -> None:
    """Age-restricted es permanente."""
    assert _is_transient_error(DownloadError("Sign in to confirm your age")) is False
    assert _is_transient_error(DownloadError("Video is age-restricted")) is False


def test_permanent_removed_message() -> None:
    """Video eliminado es permanente."""
    assert _is_transient_error(DownloadError("This video has been removed")) is False


def test_permanent_extractor_error() -> None:
    """ExtractorError genérico es permanente."""
    assert _is_transient_error(ExtractorError("Video unavailable")) is False


# ------------------- download_one — retry logic -------------------


def test_retry_succeeds_after_transient_failures(tmp_path: Path) -> None:
    """Si _try_download falla N veces transitoriamente y luego funciona, retornar success."""
    config = _make_config(tmp_path, max_retries=3)
    entry = _make_entry()
    info = _make_info()

    call_count = {"n": 0}

    def fake_try(e, c, t):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise ConnectionError("network down")
        # Tercera vez: éxito
        from yt_links_mp3.downloader import DownloadResult
        return DownloadResult(
            entry=e, success=True, output_path=str(tmp_path / "out.mp3"),
            error=None, skipped=False, metadata=None, attempts=1,
        )

    with patch("yt_links_mp3.downloader._try_download", side_effect=fake_try):
        result = download_one(entry, config, track_number=1)

    assert result.success is True
    assert call_count["n"] == 3
    assert result.attempts == 3


def test_retry_fails_after_max_attempts_on_transient(tmp_path: Path) -> None:
    """Si se acaban los reintentos en error transitorio, retorna failure."""
    config = _make_config(tmp_path, max_retries=2)
    entry = _make_entry()

    def always_fail(e, c, t):
        raise ConnectionError("network down")

    with patch("yt_links_mp3.downloader._try_download", side_effect=always_fail):
        result = download_one(entry, config, track_number=1)

    assert result.success is False
    assert "network down" in (result.error or "")
    assert result.attempts == 2


def test_no_retry_on_permanent_error(tmp_path: Path) -> None:
    """En error permanente, NO reintentar — falla inmediatamente."""
    config = _make_config(tmp_path, max_retries=5)
    entry = _make_entry()

    call_count = {"n": 0}

    def fail_permanent(e, c, t):
        call_count["n"] += 1
        raise DownloadError("Video is private")

    with patch("yt_links_mp3.downloader._try_download", side_effect=fail_permanent):
        result = download_one(entry, config, track_number=1)

    assert result.success is False
    assert call_count["n"] == 1  # Solo un intento, no reintenta
    assert result.attempts == 1
    assert "private" in (result.error or "").lower()


def test_single_attempt_succeeds(tmp_path: Path) -> None:
    """Caso normal: funciona al primer intento."""
    config = _make_config(tmp_path, max_retries=3)
    entry = _make_entry()

    from yt_links_mp3.downloader import DownloadResult

    def succeed(e, c, t):
        return DownloadResult(
            entry=e, success=True, output_path=str(tmp_path / "out.mp3"),
            error=None, skipped=False, metadata=None, attempts=1,
        )

    with patch("yt_links_mp3.downloader._try_download", side_effect=succeed):
        result = download_one(entry, config, track_number=1)

    assert result.success is True
    assert result.attempts == 1


# ------------------- download_one — skip existing -------------------


def test_skip_when_target_exists(tmp_path: Path) -> None:
    """Si el archivo ya existe y --force=False, skip."""
    config = _make_config(tmp_path)
    entry = _make_entry("dQw4w9WgXcQ")
    info = _make_info("dQw4w9WgXcQ")

    # Pre-crear el archivo que se generaría
    existing = tmp_path / "01 - Test Artist - Test Song.mp3"
    existing.touch()

    def fake_extract_info(url, download=True):
        return info

    class FakeYDL:
        def __init__(self, opts): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def extract_info(self, url, download=True):
            return fake_extract_info(url, download)

    with patch("yt_links_mp3.downloader.YoutubeDL", FakeYDL):
        result = download_one(entry, config, track_number=1)

    assert result.success is True
    assert result.skipped is True
    assert result.attempts == 1


def test_no_skip_with_force(tmp_path: Path) -> None:
    """Si --force=True, NO skip aunque el archivo exista."""
    config = _make_config(tmp_path, force=True)
    entry = _make_entry("dQw4w9WgXcQ")
    info = _make_info("dQw4w9WgXcQ")

    existing = tmp_path / "01 - Test Artist - Test Song.mp3"
    existing.touch()

    class FakeYDL:
        def __init__(self, opts): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def extract_info(self, url, download=True):
            return info
        def download(self, urls): pass

    with patch("yt_links_mp3.downloader.YoutubeDL", FakeYDL):
        result = download_one(entry, config, track_number=1)

    # No skip — pasa a download_real, que el FakeYDL.mock() va a "completar"
    # pero como no escribe archivo, igual retorna success=True (download_one no falla)
    assert result.skipped is False


# ------------------- download_all — concurrencia -------------------


def test_download_all_dry_run() -> None:
    """dry_run=True no llama a _try_download."""
    config = Config(dry_run=True)
    entries = [_make_entry("a"), _make_entry("b")]
    results = download_all(entries, config)
    assert len(results) == 2
    assert all(r.success and r.error == "dry-run" for r in results)


def test_download_all_runs_concurrently(tmp_path: Path) -> None:
    """download_all usa ThreadPoolExecutor, no loop serie."""
    import threading
    import time

    config = _make_config(tmp_path, concurrency=3, max_retries=1)
    entries = [_make_entry(f"id{i:011d}") for i in range(3)]

    threads_seen = set()

    def fake_try(e, c, t):
        threads_seen.add(threading.get_ident())
        time.sleep(0.05)  # Para forzar overlap
        from yt_links_mp3.downloader import DownloadResult
        return DownloadResult(
            entry=e, success=True, output_path=None,
            error=None, skipped=False, metadata=None, attempts=1,
        )

    with patch("yt_links_mp3.downloader._try_download", side_effect=fake_try):
        results = download_all(entries, config)

    assert len(results) == 3
    assert all(r.success for r in results)
    # Si fuera serie, solo habria 1 thread. Si es paralelo, 3.
    assert len(threads_seen) >= 2


# ------------------- write_failed_links -------------------


def test_write_failed_links_writes_only_failures(tmp_path: Path) -> None:
    failed_file = tmp_path / "failed.txt"
    from yt_links_mp3.downloader import DownloadResult

    results = [
        DownloadResult(entry=_make_entry("a"), success=True, output_path="x", error=None),
        DownloadResult(entry=_make_entry("b"), success=False, output_path=None, error="boom"),
        DownloadResult(entry=_make_entry("c"), success=False, output_path=None, error="nope"),
    ]
    count = write_failed_links(results, str(failed_file))
    assert count == 2
    content = failed_file.read_text()
    assert "boom" not in content  # no incluye el successful
    assert "_b" in content or "id_b" in content or "youtu.be/b" in content


def test_write_failed_links_no_failures(tmp_path: Path) -> None:
    """Si no hay failures, no escribe archivo."""
    failed_file = tmp_path / "failed.txt"
    from yt_links_mp3.downloader import DownloadResult

    results = [
        DownloadResult(entry=_make_entry("a"), success=True, output_path="x", error=None),
    ]
    count = write_failed_links(results, str(failed_file))
    assert count == 0
    assert not failed_file.exists()