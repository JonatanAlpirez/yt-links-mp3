"""Descargador: orquesta yt-dlp + ffmpeg para cada link."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from yt_dlp import YoutubeDL

from .config import Config
from .linklist import LinkEntry
from .metadata import TrackMetadata, build_metadata
from .paths import build_filename, ensure_unique_path


@dataclass
class DownloadResult:
    entry: LinkEntry
    success: bool
    output_path: str | None
    error: str | None
    skipped: bool = False  # True si fue skip por nombre existente
    metadata: TrackMetadata | None = None


def _ydl_opts(config: Config, output_template: str) -> dict:
    """Opciones comunes para yt-dlp.

    output_template es el template ya resuelto para ESTE video (con track_number,
    artist, title). yt-dlp lo expande a un path final.
    """
    return {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": config.audio_format,
                "preferredquality": str(config.audio_quality),
            }
            # Si embed_thumbnail=True, yt-dlp embebe la thumbnail automáticamente
            # cuando detecta ffmpeg disponible.
        ],
        "outtmpl": str(config.output_dir / output_template),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # yt-dlp escribe info.json al lado del MP3 si queremos inspeccionar
        "writeinfojson": False,
        # Descargar thumbnail para embeber (Fase 2)
        "writethumbnail": config.embed_thumbnail,
        # Post-processor adicional para embeber cover en MP3
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


def _resolve_output_path(
    entry: LinkEntry, track_number: int, info: dict, config: Config
) -> Path:
    """Resuelve el path final del archivo usando metadata + template."""
    metadata = _build_metadata_for_entry(entry, track_number, info, config)
    filename = build_filename(config.filename_template, metadata, ext=config.audio_format)
    return config.output_dir / filename


def download_one(
    entry: LinkEntry,
    config: Config,
    track_number: int,
    prebuilt_info: dict | None = None,
) -> DownloadResult:
    """Descarga un solo entry.

    prebuilt_info: si se pasa, no se vuelve a llamar a extract_info (evita doble
    request cuando ya tenemos la metadata del listing).
    """
    config.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if prebuilt_info is not None:
            info = prebuilt_info
            metadata = _build_metadata_for_entry(entry, track_number, info, config)
            target_filename = build_filename(
                config.filename_template, metadata, ext=config.audio_format
            )
            target_path = config.output_dir / target_filename
        else:
            # Sin info previa: necesitamos el metadata para el outtmpl antes de descargar.
            # Hacemos un extract_info sin download para conseguir metadata.
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
            )

        # Asegurar path único si --force y existe
        if config.force and target_path.exists():
            target_path = ensure_unique_path(target_path)

        # outtmpl para esta descarga específica: solo el nombre (sin track_number
        # porque yt-dlp no puede interpolar {track_number} — eso lo hicimos nosotros).
        outtmpl = str(target_path.with_suffix("")) + ".%(ext)s"
        opts = _ydl_opts(config, "")
        opts["outtmpl"] = outtmpl
        # Forzar que no descargue el formato contenedor original — solo audio
        opts["format"] = "bestaudio/best"

        with YoutubeDL(opts) as ydl:
            logger.debug(f"Descargando {entry.url} → {target_path.name}")
            ydl.download([entry.url])

        # Verificar que el archivo final existe (post-conversión a mp3)
        if not target_path.exists():
            # yt-dlp pudo haber escrito a un nombre ligeramente diferente
            # (por ejemplo, extensión pre-conversión). Buscar alternativas.
            stem = target_path.stem
            candidates = list(config.output_dir.glob(f"{stem}.*"))
            if candidates:
                target_path = candidates[0]

        return DownloadResult(
            entry=entry,
            success=True,
            output_path=str(target_path),
            error=None,
            skipped=False,
            metadata=metadata,
        )
    except Exception as e:  # noqa: BLE001 - queremos capturar todo yt-dlp
        logger.error(f"Falló {entry.url}: {e}")
        return DownloadResult(
            entry=entry,
            success=False,
            output_path=None,
            error=str(e),
            skipped=False,
            metadata=None,
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

    results: list[DownloadResult] = []
    with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
        # Pasar el track_number como índice+1
        future_to_entry = {
            executor.submit(download_one, entry, config, idx + 1): entry
            for idx, entry in enumerate(entries)
        }
        for future in as_completed(future_to_entry):
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