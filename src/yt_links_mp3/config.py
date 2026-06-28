"""Config con pydantic + YAML."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .metadata import DEFAULT_CLEANUP_PATTERNS


class Config(BaseModel):
    """Config principal del CLI."""

    output_dir: Path = Field(default=Path.home() / "Music" / "Downloads")
    audio_format: str = "mp3"
    audio_quality: int = 320  # kbps — máximo para MP3 (CBR)
    concurrency: int = 3
    # Reintentos en errores transitorios (network, 5xx, timeout).
    # Errores permanentes (404, privado, eliminado, age-restricted) no se reintentan.
    max_retries: int = 3
    # Base del backoff exponencial (segundos). Backoffs: base * 5^(attempt-1)
    # Default 1.0 → 1s, 5s, 15s.
    retry_backoff_base: float = 1.0
    skip_existing: bool = True
    force: bool = False
    dry_run: bool = False
    embed_thumbnail: bool = True
    # Template para el nombre del archivo. Placeholders:
    # {track_number}, {artist}, {title}, {video_id}, {ext}
    filename_template: str = "{track_number:02d} - {artist} - {title}.{ext}"
    # Patrones regex (case-insensitive) a borrar del título al limpiar
    cleanup_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_CLEANUP_PATTERNS))
    failed_filename: str = "links.txt.failed"

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        """Carga config desde YAML. Si no hay path o no existe, devuelve defaults."""
        if path is None:
            return cls()
        file_path = Path(path)
        if not file_path.exists():
            return cls()
        data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        # Expandir ~ en output_dir si viene como string
        if "output_dir" in data and isinstance(data["output_dir"], str):
            data["output_dir"] = Path(data["output_dir"]).expanduser()
        return cls(**data)