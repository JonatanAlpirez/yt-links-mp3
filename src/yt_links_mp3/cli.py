"""CLI entrypoint con click."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click
from loguru import logger

from .config import Config
from .downloader import download_all, write_failed_links
from .linklist import parse_link_file
from .logging import setup_logging
from .progress import progress_bar


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Logging nivel DEBUG")
@click.option(
    "-c", "--config", "config_path", type=click.Path(), default=None, help="Path al config.yaml"
)
@click.pass_context
def main(ctx: click.Context, verbose: bool, config_path: str | None) -> None:
    """yt-links-mp3 — descargador de música desde YouTube vía archivo de links."""
    setup_logging(verbose=verbose)
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.load(config_path)


@main.command()
@click.argument("links_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output-dir", type=click.Path(path_type=Path), default=None)
@click.option("--concurrency", type=int, default=None)
@click.option("--dry-run", is_flag=True, default=None)
@click.option("--force", is_flag=True, default=None)
@click.pass_context
def download(
    ctx: click.Context,
    links_file: Path,
    output_dir: Path | None,
    concurrency: int | None,
    dry_run: bool | None,
    force: bool | None,
) -> None:
    """Descarga todos los links de LINKS_FILE."""
    config: Config = ctx.obj["config"]

    # Overrides de CLI
    if output_dir is not None:
        config.output_dir = output_dir.expanduser()
    if concurrency is not None:
        config.concurrency = concurrency
    if dry_run is not None:
        config.dry_run = dry_run
    if force is not None:
        config.force = force

    logger.info(f"Parseando {links_file}")
    result = parse_link_file(links_file)

    # Reportar skips
    if result.skipped:
        logger.warning(f"{len(result.skipped)} líneas ignoradas:")
        for line_no, raw, reason in result.skipped:
            logger.warning(f"  línea {line_no}: {reason}  ({raw.strip()[:60]})")

    if not result.entries:
        logger.error("No hay links válidos para descargar")
        raise click.Abort()

    logger.info(f"{result.total} links únicos → {config.output_dir}")

    if config.dry_run:
        logger.info("[dry-run] NO se descargará nada, solo previsualización")
        for e in result.entries:
            logger.info(f"  - {e.url}  ({e.description or 'sin descripción'})")
        return

    logger.info(f"Descargando con concurrencia={config.concurrency}")
    with progress_bar(result.total, description="Descargando") as progress:
        task_id = progress.tasks[0].id
        results = download_all(result.entries, config)
        progress.update(task_id, completed=result.total)

    success = sum(1 for r in results if r.success and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    failed = [r for r in results if not r.success]
    retries = sum(r.attempts - 1 for r in results if r.success and r.attempts > 1)

    parts = [f"✅ {success} descargados"]
    if skipped:
        parts.append(f"⏭️  {skipped} ya existían")
    if retries:
        parts.append(f"🔄 {retries} requirieron retry")
    logger.info(", ".join(parts))

    if failed:
        failed_path = config.output_dir / config.failed_filename
        count = write_failed_links(results, str(failed_path))
        logger.warning(f"⚠️  {count} fallidos → {failed_path}")
        logger.info(f"Reintentá con: yt-links-mp3 download {failed_path}")
        raise click.Abort()
    else:
        logger.info("🎉 Todos los links procesados OK")


@main.command()
@click.argument("links_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def validate(ctx: click.Context, links_file: Path) -> None:
    """Valida LINKS_FILE sin descargar nada. Muestra resumen."""
    config: Config = ctx.obj["config"]  # noqa: F841 - usado implícitamente
    result = parse_link_file(links_file)

    click.echo(f"\n📄 {links_file}")
    click.echo(f"   {result.total} links únicos")
    if result.skipped:
        click.echo(f"   ⚠️  {len(result.skipped)} líneas ignoradas:")
        for line_no, raw, reason in result.skipped:
            click.echo(f"      línea {line_no}: {reason}  ({raw.strip()[:60]})")

    if result.entries:
        click.echo("\n   Links a descargar:")
        for e in result.entries[:10]:
            desc = f" — {e.description}" if e.description else ""
            click.echo(f"      • {e.url}{desc}")
        if len(result.entries) > 10:
            click.echo(f"      ... y {len(result.entries) - 10} más")
    click.echo()


def _is_url_like(arg: str) -> bool:
    """Detecta si un argumento parece URL/ID de YouTube o ruta a archivo."""
    if "://" in arg or arg.startswith("youtu.be/"):
        return True
    # ID solo de 11 chars
    import re as _re

    if _re.match(r"^[A-Za-z0-9_-]{11}$", arg):
        return True
    return False


def _format_duration(seconds: int | float | None) -> str:
    """Formatea segundos a M:SS o H:MM:SS según corresponda.

    Ejemplos:
        213 (3:33)         → '3:33'
        3599 (59:59)       → '59:59'
        3600 (1:00:00)     → '1:00:00'
        3930 (1h 5m 30s)   → '1:05:30'
        None o 0           → '?'
    """
    if not seconds:
        return "?"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def _existing_path_for(
    entry_video_id: str,
    metadata_artist: str,
    metadata_title: str,
    track_number: int,
    config: Config,
) -> Path | None:
    """Devuelve el path final esperado si ya existe en disco, si no None."""
    from yt_links_mp3.metadata import build_metadata
    from yt_links_mp3.paths import build_filename

    info = {
        "uploader": metadata_artist,
        "title": metadata_title,
    }
    md = build_metadata(
        info=info,
        track_number=track_number,
        video_id=entry_video_id,
        cleanup_patterns=config.cleanup_patterns,
    )
    md.artist = metadata_artist  # no usar el limpiado, queremos matchear el filename
    filename = build_filename(config.filename_template, md, ext=config.audio_format)
    target = config.output_dir / filename
    return target if target.exists() else None


@main.command()
@click.argument("target")
@click.pass_context
def info(ctx: click.Context, target: str) -> None:
    """Muestra metadata de TARGET sin descargar.

    TARGET puede ser:
      - Una URL de YouTube (https://...)
      - Un ID de video de 11 caracteres
      - Un archivo .txt con múltiples links (mismo formato que download)
    """
    config: Config = ctx.obj["config"]

    if _is_url_like(target):
        # Una sola URL
        from .downloader import build_cache, fetch_metadata_cached
        from .metadata import build_metadata

        url = target if "://" in target else f"https://youtu.be/{target}"
        cache = build_cache(config)
        try:
            raw_info = fetch_metadata_cached(url, cache=cache)
        except Exception as e:  # noqa: BLE001
            click.echo(f"❌ No pude obtener metadata de {url}: {e}", err=True)
            raise click.Abort() from None  # noqa: B904

        md = build_metadata(
            info=raw_info,
            track_number=1,
            video_id=raw_info.get("id", "?"),
            cleanup_patterns=config.cleanup_patterns,
        )

        click.echo(f"\n🎬 {raw_info.get('title', '?')}")
        click.echo(f"   Canal:    {raw_info.get('uploader') or raw_info.get('channel') or '?'}")
        click.echo(f"   Artista:  {md.artist}")
        click.echo(f"   Titulo:   {md.title}")
        click.echo(f"   Duracion: {_format_duration(raw_info.get('duration'))}")
        click.echo(f"   ID:       {raw_info.get('id', '?')}")

        # Detectar si ya está descargado
        video_id = raw_info.get("id", "?")
        existing = _existing_path_for(
            entry_video_id=video_id,
            metadata_artist=md.artist,
            metadata_title=md.title,
            track_number=1,
            config=config,
        )
        click.echo()
        if existing is not None:
            click.echo(f"   ✓ Ya descargado: {existing.name}")
        else:
            click.echo(f"   — No descargado todavía")

        click.echo()
    else:
        # Archivo de links
        from .downloader import build_cache, fetch_metadata_cached
        from .linklist import parse_link_file

        path = Path(target)
        if not path.exists():
            click.echo(f"❌ Archivo no encontrado: {path}", err=True)
            raise click.Abort()

        result = parse_link_file(path)
        if result.skipped:
            click.echo(f"⚠️  {len(result.skipped)} líneas ignoradas en {path}")
        if not result.entries:
            click.echo("No hay links válidos para mostrar")
            return

        cache = build_cache(config)
        rows: list[tuple[str, str, str, str, str] | None] = [None] * len(result.entries)

        def fetch_one(idx: int, entry) -> tuple[int, tuple[str, str, str, str, str]]:
            """Fetch metadata + detect existing file for one entry.

            Devuelve (idx, row) para que el caller preserva el orden de las filas
            al asignar rows[idx - 1] = row aunque los futures completen desordenados.
            """
            try:
                info_dict = fetch_metadata_cached(entry.url, cache=cache)
                from .metadata import build_metadata

                md = build_metadata(
                    info=info_dict,
                    track_number=idx,
                    video_id=entry.video_id,
                    hint=entry.description,
                    cleanup_patterns=config.cleanup_patterns,
                )
                existing = _existing_path_for(entry.video_id, md.artist, md.title, idx, config)
                downloaded = "✓" if existing else "—"
                return (
                    idx,
                    (
                        str(idx),
                        md.artist,
                        md.title,
                        _format_duration(info_dict.get("duration")),
                        downloaded,
                    ),
                )
            except Exception as e:  # noqa: BLE001
                return (idx, (str(idx), "?", entry.url[:40], "?", f"err: {e}"))

        with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
            futures = {
                executor.submit(fetch_one, idx, entry): idx
                for idx, entry in enumerate(result.entries, start=1)
            }
            for future in as_completed(futures):
                idx, row = future.result()
                rows[idx - 1] = row

        rows = [r for r in rows if r is not None]

        # Tabla con rich si esta disponible, si no, click.echo simple
        try:
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(show_header=True, header_style="bold")
            table.add_column("#", width=3)
            table.add_column("Artista", style="cyan")
            table.add_column("Titulo", style="green")
            table.add_column("Duracion", justify="right")
            table.add_column("Descargado", justify="center")
            for row in rows:
                table.add_row(*row)
            console.print(table)
        except ImportError:
            click.echo(f"\n{'#':<3} {'Artista':<25} {'Titulo':<40} {'Dur':>6}  Descargado")
            for row in rows:
                click.echo(f"{row[0]:<3} {row[1]:<25} {row[2]:<40} {row[3]:>6}  {row[4]}")
            click.echo()


if __name__ == "__main__":
    main()
