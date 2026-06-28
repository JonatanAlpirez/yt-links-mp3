"""Extracción y limpieza de metadatos desde la info de yt-dlp."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Patrones case-insensitive a borrar del título. Cada patrón es una regex.
# Orden importa: los más específicos primero.
DEFAULT_CLEANUP_PATTERNS: list[str] = [
    r"\(official\s+video\)",
    r"\(official\s+music\s+video\)",
    r"\[official\s+video\]",
    r"\(official\)",
    r"\[official\]",
    r"\(lyric(?:s)?\s*video\)",
    r"\[lyric(?:s)?\s*video\]",
    r"\(lyric(?:s)?\)",
    r"\[lyric(?:s)?\]",
    r"\(lyrics?\)",
    r"\(hd\)",
    r"\[hd\]",
    r"\bhd\b",
    r"official\s+video",
    r"official\s+music\s+video",
    r"music\s+video",
    r"\blyric(?:s)?\s*video\b",
    r"\blyrics?\b",
]


@dataclass
class TrackMetadata:
    """Metadatos limpios para una canción."""

    artist: str
    title: str
    track_number: int
    video_id: str
    cover_url: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


def cleanup_title(title: str, patterns: list[str] | None = None) -> str:
    """Limpia un título aplicando las regex de la lista (case-insensitive).

    Ejemplos:
      "Never Gonna Give You Up (Official Video)" -> "Never Gonna Give You Up"
      "Song Name (Lyric)" -> "Song Name"
      "Song HD" -> "Song"
    """
    if not title:
        return ""
    pats = patterns if patterns is not None else DEFAULT_CLEANUP_PATTERNS
    cleaned = title
    for p in pats:
        cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE)
    # Colapsar espacios múltiples y trim
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_artist(info: dict, hint: str | None = None) -> str:
    """Extrae el artista de la info de yt-dlp. Aplica hint si está presente.

    Formatos de hint aceptados:
      - "Artist - Title" (separador guion)
      - "Artist/Title" (separador slash)
      - "Artist" solo (override completo)
    """
    if hint and ("/" in hint or " - " in hint):
        # hint formato "Artist - Title" o "Artist/Title"
        artist = re.split(r"\s*[\-/]\s*", hint, maxsplit=1)[0].strip()
        if artist:
            return artist
    if hint:
        return hint.strip()

    # yt-dlp suele poner el canal en uploader o channel
    artist = info.get("artist") or info.get("uploader") or info.get("channel")
    if artist:
        # Quitar " - Topic" que YouTube Music agrega
        artist = re.sub(r"\s*-\s*Topic$", "", artist, flags=re.IGNORECASE).strip()
        if artist:
            return artist
    return "Unknown Artist"


def extract_title(
    info: dict,
    hint: str | None = None,
    cleanup_patterns: list[str] | None = None,
) -> str:
    """Extrae el título limpio. Aplica hint si está presente, sino limpia con regex."""
    raw_title: str
    if hint and ("/" in hint or " - " in hint):
        parts = re.split(r"\s*[\-/]\s*", hint, maxsplit=1)
        if len(parts) == 2 and parts[1].strip():
            raw_title = parts[1].strip()
        else:
            raw_title = info.get("title") or info.get("fulltitle") or ""
    elif hint:
        # Hint que no matchea el formato Artist/Title: tratar como override completo
        raw_title = hint
    else:
        raw_title = info.get("title") or info.get("fulltitle") or ""

    return cleanup_title(raw_title, patterns=cleanup_patterns)


def extract_cover_url(info: dict) -> str | None:
    """Extrae la mejor URL de thumbnail disponible (maxresdefault > hqdefault)."""
    thumbnails = info.get("thumbnails") or []
    if not thumbnails:
        return None
    # Preferir maxresdefault, fallback a hqdefault, sino la última
    by_pref = {"maxresdefault": 3, "hqdefault": 2, "mqdefault": 1, "default": 0}
    best = None
    best_score = -1
    for t in thumbnails:
        url = t.get("url")
        if not url:
            continue
        score = by_pref.get(t.get("id", ""), 0)
        if score > best_score:
            best = url
            best_score = score
    return best


def build_metadata(
    info: dict,
    track_number: int,
    video_id: str,
    hint: str | None = None,
    cleanup_patterns: list[str] | None = None,
) -> TrackMetadata:
    """Construye TrackMetadata desde la info de yt-dlp + hint + número de track."""
    artist = extract_artist(info, hint=hint)
    title = extract_title(info, hint=hint, cleanup_patterns=cleanup_patterns)
    cover = extract_cover_url(info)
    return TrackMetadata(
        artist=artist or "Unknown Artist",
        title=title or video_id,
        track_number=track_number,
        video_id=video_id,
        cover_url=cover,
    )