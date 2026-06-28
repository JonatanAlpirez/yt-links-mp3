"""Descargador: orquesta yt-dlp + ffmpeg para cada link."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from yt_dlp import YoutubeDL
from yt_dlp.utils import (
    DownloadError,
    ExtractorError,
    UnavailableVideoError,
)

from .config import Config
from .linklist import LinkEntry
from .metadata import TrackMetadata, build_metadata
from .paths import build_filename, ensure_unique_path


# Errores que yt-dlp lanza cuando el video NO está disponible (no reintentar).
# Estos son permanentes: reintentar no va a cambiar el resultado.
_PERMANENT_ERROR_TYPES: tuple[type[Exception], ...] = (
    UnavailableVideoError,
)

# Mensajes de error que indican que NO vale la pena reintentar (permanentes).
_PERMANENT_ERROR_MESSAGES: tuple[str, ...] = (
    "private video",
    "video is private",
    "this video is not available",
    "video unavailable",
    "this video has been removed",
    "account associated with this video",
    "sign in to confirm your age",
    "age-restricted",
    "this video is no longer available",
    "http error 404",
    "404 not found",
)


@dataclass
class DownloadResult:
    entry: LinkEntry
    success: bool
    output_path: str | None
    error: str | None
    skipped: bool = False  # True si fue skip por nombre existente
    metadata: TrackMetadata | None = None
    attempts: int = 1  # Cuántos intentos tomó (1 = sin retry)


def _is_transient_error(exc: Exception) -> bool:
    """Devuelve True si el error parece transitorio (vale la pena reintentar).

    Errores transitorios: network, timeouts, 5xx HTTP, errores genéricos.
    Errores permanentes: video privado, eliminado, 404, age-restricted.
    """
    # Tipo de excepción conocido como permanente
    if isinstance(exc, _PERMANENT_ERROR_TYPES):
        return False
    # yt-dlp envuelve la mayoría de errores en DownloadError; revisamos el mensaje
    msg = str(exc).lower()
    for permanent_msg in _PERMANENT_ERROR_MESSAGES:
        if permanent_msg in msg:
            return False
    # Cualquier otra cosa: tratar como transitorio (red, timeout, 5xx, etc.)
    return True


def _ydl_opts(config: Config, output_template: str) -> dict:
    """Opciones comunes para yt-dlp."""
    return {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": config.audio_format,
                "preferredquality": str(config.audio_quality),
            }
        ],
        "outtmpl": str(config.output_dir / output_template),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "writeinfojson": False,
        "writethumbnail": config.embed_thumbnail,
        "postprocessor_args": {
            "ffmpeg_o": ["-id3v2_version", "4"],
        } if config.embed_thumbnail else {},
    }


def _build_metadata_for_entry(
    entry: LinkEntry, track_number: int, info: dict, config: Config
) -> TrackMetadata:
    """Construye TrackMetadata para un entry usando la info extraída."""
    return build_metadata(
        info=info,
        track_number=track_number,
        video_id=entry.video_id,
        hint=entry.description,
        cleanup_patterns=config.cleanup_patterns,
    )


def _try_download(entry: LinkEntry, config: Config, track_number: int) -> DownloadResult:
    """Intenta descargar un entry UNA vez (sin retry). Lanza excepción si falla."""
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # 1) Extract info sin descargar para conseguir metadata
    with YoutubeDL(_ydl_opts(config, "%(id)s.%(ext)s")) as ydl:
        info = ydl.extract_info(entry.url, download=False)

    metadata = _build_metadata_for_entry(entry, track_number, info, config)
    target_filename = build_filename(
        config.filename_template, metadata, ext=config.audio_format
    )
    target_path = config.output_dir / target_filename

    # Skip si ya existe (a menos que --force)
    if target_path.exists() and not config.force:
        logger.info(f"⏭️  Skip {entry.url} → {target_path.name} ya existe")
        return DownloadResult(
            entry=entry,
            success=True,
            output_path=str(target_path),
            error=None,
            skipped=True,
            metadata=metadata,
            attempts=1,
        )

    # Asegurar path único si --force y existe
    if config.force and target_path.exists():
        target_path = ensure_unique_path(target_path)

    # 2) Descargar con el template final (nombre ya resuelto)
    outtmpl = str(target_path.with_suffix("")) + ".%(ext)s"
    opts = _ydl_opts(config, "")
    opts["outtmpl"] = outtmpl
    opts["format"] = "bestaudio/best"

    with YoutubeDL(opts) as ydl:
        logger.debug(f"Descargando {entry.url} → {target_path.name}")
        ydl.download([entry.url])

    # Verificar archivo final
    if not target_path.exists():
        # yt-dlp pudo haber escrito a un nombre ligeramente diferente
        stem = target_path.stem
        candidates = list(config.output_dir.glob(f"{stem}.*"))
        if candidates:
            target_path = candidates[0]
        else:
            raise DownloadError(f"Archivo final no encontrado: {target_path}")

    return DownloadResult(
        entry=entry,
        success=True,
        output_path=str(target_path),
        error=None,
        skipped=False,
        metadata=metadata,
        attempts=1,
    )


def download_one(
    entry: LinkEntry,
    config: Config,
    track_number: int,
) -> DownloadResult:
    """Descarga un entry con reintentos y backoff exponencial.

    Reintenta hasta `config.max_retries` veces en errores transitorios.
    En errores permanentes (video privado, eliminado, 404, age-restricted)
    no reintenta — falla inmediatamente.
    """
    max_retries = max(1, config.max_retries)
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            result = _try_download(entry, config, track_number)
            if attempt > 1:
                logger.info(f"✅ {entry.url} exitoso en intento {attempt}/{max_retries}")
            return DownloadResult(
                entry=result.entry,
                success=result.success,
                output_path=result.output_path,
                error=result.error,
                skipped=result.skipped,
                metadata=result.metadata,
                attempts=attempt,
            )
        except Exception as e:  # noqa: BLE001 - capturar todo yt-dlp
            last_exc = e
            is_transient = _is_transient_error(e)

            if not is_transient:
                logger.error(f"⛔ {entry.url} falló (error permanente): {e}")
                break

            if attempt >= max_retries:
                logger.error(
                    f"❌ {entry.url} falló tras {attempt}/{max_retries} intentos: {e}"
                )
                break

            # Backoff: 1s, 5s, 15s (configurable vía retry_backoff_base)
            backoff = config.retry_backoff_base * (5 ** (attempt - 1))
            logger.warning(
                f"⚠️  {entry.url} intento {attempt}/{max_retries} falló: {e}. "
                f"Reintentando en {backoff:.0f}s..."
            )
            time.sleep(backoff)

    return DownloadResult(
        entry=entry,
        success=False,
        output_path=None,
        error=str(last_exc) if last_exc else "unknown error",
        skipped=False,
        metadata=None,
        attempts=attempt if last_exc else 1,
    )


def download_all(entries: list[LinkEntry], config: Config) -> list[DownloadResult]:
    """Descarga todos los entries con concurrencia del config."""
    if config.dry_run:
        logger.info(f"[dry-run] {len(entries)} links NO se descargarán")
        for e in entries:
            logger.info(f"  - {e.url}  ({e.description or 'sin descripción'})")
        return [
            DownloadResult(
                entry=e,
                success=True,
                output_path=None,
                error="dry-run",
                skipped=False,
                metadata=None,
            )
            for e in entries
        ]

    # Asignar track_number a cada entry según orden en el archivo
    indexed = [(idx + 1, entry) for idx, entry in enumerate(entries)]

    results: list[DownloadResult] = []
    with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
        future_to_idx = {
            executor.submit(download_one, entry, config, idx): idx
            for idx, entry in indexed
        }
        for future in as_completed(future_to_idx):
            result = future.result()
            results.append(result)

    return results


def write_failed_links(results: list[DownloadResult], output_path: str) -> int:
    """Escribe los links fallidos a un archivo para reintentar. Devuelve cuántos escribió."""
    failed = [r for r in results if not r.success]
    if not failed:
        return 0
    lines = ["# Links fallidos - reintentá con: yt-links-mp3 download <este archivo>\n"]
    for r in failed:
        lines.append(f"{r.entry.url}    {r.entry.description or ''}\n")
    Path(output_path).write_text("".join(lines), encoding="utf-8")
    return len(failed)