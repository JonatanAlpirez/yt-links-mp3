"""Config con pydantic + YAML."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Config(BaseModel):
    """Config principal del CLI."""

    output_dir: Path = Field(default=Path.home() / "Music" / "Downloads")
    audio_format: str = "mp3"
    audio_quality: int = 320  # kbps — máximo para MP3 (CBR)
    concurrency: int = 3
    skip_existing: bool = True
    force: bool = False
    dry_run: bool = False
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    filename_template: str = "{artist}/{album}/{track_number:02d} - {title}.{ext}"
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