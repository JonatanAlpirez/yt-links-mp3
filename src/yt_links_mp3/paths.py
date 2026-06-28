"""Sanitización de nombres de archivo y plantillas."""
from __future__ import annotations

import re
from pathlib import Path

from .metadata import TrackMetadata

# Caracteres prohibidos en nombres de archivo (Windows + Mac + Linux en general)
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Nombres reservados en Windows
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# Longitud máxima conservadora (la mayoría de FS aguantan 255, dejamos margen)
_MAX_COMPONENT_LENGTH = 200


def sanitize_component(name: str) -> str:
    """Sanitiza un componente individual de path (artista, álbum, título)."""
    if not name:
        return "_"

    # Reemplazar forbiddens por _
    cleaned = _FORBIDDEN.sub("_", name)

    # Trim whitespace y puntos al final (problemático en Windows)
    cleaned = cleaned.strip().strip(".")

    # Reemplazar reserved names
    if cleaned.upper() in _RESERVED:
        cleaned = f"_{cleaned}"

    # Cap longitud
    if len(cleaned) > _MAX_COMPONENT_LENGTH:
        cleaned = cleaned[:_MAX_COMPONENT_LENGTH].rstrip()

    return cleaned or "_"


def sanitize_template(template: str, context: dict[str, str | int]) -> str:
    """Aplica una plantilla tipo '{artist} - {title}.{ext}'
    con sanitización de cada componente.

    Soporta formato simple: {key}, {key:0Nd} para zero-padding.
    """
    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if ":" in token:
            key, fmt = token.split(":", 1)
            raw_value = context.get(key, "_")
            try:
                if fmt.endswith("d") and fmt[:-1].isdigit():
                    width = int(fmt[:-1])
                    return str(int(raw_value)).zfill(width)
            except (ValueError, TypeError):
                pass
            return str(raw_value)
        # Sanitizar el valor ANTES de meterlo en el template,
        # para que / no rompa la estructura de subcarpetas
        return sanitize_component(str(context.get(token, "_")))

    # Sustituir placeholders con valores ya sanitizados
    result = re.sub(r"\{([^}]+)\}", replace, template)

    # Sanitizar los segmentos literales del template (no los placeholders)
    parts = result.split("/")
    return "/".join(sanitize_component(p) for p in parts)


def ensure_unique_path(path: Path) -> Path:
    """Si el path ya existe, agrega sufijo numérico hasta encontrar uno libre."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def build_filename(template: str, metadata: TrackMetadata, ext: str = "mp3") -> Path:
    """Construye el filename final a partir de un template y la metadata.

    El template usa {track_number}, {artist}, {title}, {video_id}, {ext}.
    Aplica sanitización a cada componente.

    Devuelve solo el nombre (no la ruta completa); el caller lo une con output_dir.
    """
    context = {
        "track_number": metadata.track_number,
        "artist": metadata.artist,
        "title": metadata.title,
        "video_id": metadata.video_id,
        "ext": ext,
    }
    # Asegurar que .ext esté incluido si el template no lo trae
    if "{ext}" not in template:
        template_with_ext = f"{template}.{ext}"
    else:
        template_with_ext = template
    filename = sanitize_template(template_with_ext, context)
    return Path(filename)