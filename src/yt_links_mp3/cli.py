"""CLI entrypoint con click."""
from __future__ import annotations

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

    from .downloader import download_all

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


if __name__ == "__main__":
    main()