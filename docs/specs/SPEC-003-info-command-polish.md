# SPEC-003: Info command polish — URL status, duration formatting, and concurrency

| Campo | Valor |
|---|---|
| **ID** | SPEC-003 |
| **Título** | Tres mejoras al comando `info`: estado descargado en URL, formateo de duración con horas, y concurrencia en archivo |
| **Severidad** | 🟡 Media (UX, inconsistencia entre comandos y docs) |
| **Estado** | ✅ Done (implementado en `548f7e5`) |
| **Archivos afectados** | `src/yt_links_mp3/cli.py`, `tests/test_cli.py` |
| **Esfuerzo estimado** | 45–60 min |
| **Riesgo de regresión** | Bajo (solo toca `cli.py` y tests; no toca lógica de descarga) |

---

## 1. Contexto

Este spec reemplaza y consolida tres issues de calidad de vida encontrados en el análisis post-Phase 5. Los tres afectan al comando `info` y son independientes entre sí pero comparten archivo y tipo de cambio (UX/output del CLI).

---

## 2. Feature A — `info <URL>` debe mostrar estado "ya descargado"

### 2.1 Problema

El comando `info` tiene dos modos según el argumento:

| Argumento | Comportamiento actual | Indicador "Descargado" |
|---|---|---|
| `info <URL>` | Muestra título, artista, duración, ID | ❌ **No se muestra** |
| `info <archivo.txt>` | Tabla con N, Artista, Título, Duración, Descargado | ✅ Se muestra ✓/— |

El README (`README.md:339`) promete:

> Muestra título, artista, duración y si ya está descargado, sin tocar disco.

La promesa se cumple solo para la rama de archivo. Para una URL o ID suelto, el usuario no sabe si el video ya está en `output_dir`.

### 2.2 Solución

Reusar `_existing_path_for` (`cli.py:153-177`) en la rama URL, pasando `track_number=1` como placeholder.

**Output después del fix:**

```
🎬 Never Gonna Give You Up
   Canal:    Rick Astley
   Artista:  Rick Astley
   Titulo:   Never Gonna Give You Up
   Duracion: 3:33
   ID:       dQw4w9WgXcQ

   ✓ Ya descargado: 01 - Rick Astley - Never Gonna Give You Up.mp3
```

O, si no está descargado:

```
   — No descargado todavía
```

### 2.3 Criterios de aceptación

- [ ] `info <URL>` muestra `✓ Ya descargado: <filename>` cuando el archivo existe en `output_dir`.
- [ ] `info <URL>` muestra `— No descargado todavía` cuando el archivo NO existe.
- [ ] `info <ID de 11 chars>` tiene el mismo comportamiento.
- [ ] Si el template custom no incluye `{track_number}`, sigue funcionando.

---

## 3. Feature B — `_format_duration` debe manejar horas correctamente

### 3.1 Problema

La función `_format_duration` (`cli.py:144-150`) retorna formato incorrecto para duraciones ≥ 1 hora:

```python
>>> _format_duration(65 * 60 + 30)  # 1h 5m 30s
'65:30'   # ← Incorrecto. Debería ser '1:05:30'
```

Casos afectados:

| Contenido | Duración | Actual | Esperada |
|---|---|---|---|
| Live set DJ | 1h 30m | `90:00` | `1:30:00` |
| Podcast | 2h 15m | `135:00` | `2:15:00` |
| Mix largo | 3h 45m 20s | `225:20` | `3:45:20` |
| Video normal (≤1h) | 3:33 | `3:33` | `3:33` (no cambia) |

### 3.2 Solución

Formato adaptativo: `H:MM:SS` (≥ 1h) o `M:SS` (< 1h).

```python
def _format_duration(seconds: int | float | None) -> str:
    """Formatea segundos a M:SS o H:MM:SS según corresponda."""
    if not seconds:
        return "?"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"
```

Casos de prueba:

| Input | Output |
|---|---|
| `None` | `?` |
| `0` | `?` |
| `59` | `0:59` |
| `60` | `1:00` |
| `213` | `3:33` |
| `3599` | `59:59` |
| `3600` | `1:00:00` |
| `3661` | `1:01:01` |
| `3930` | `1:05:30` |
| `7325` | `2:02:05` |
| `36000` | `10:00:00` |

### 3.3 Criterios de aceptación

- [ ] `_format_duration(3930)` retorna `"1:05:30"`.
- [ ] `_format_duration(213)` retorna `"3:33"` (sin cambio para < 1h).
- [ ] `_format_duration(None)` retorna `"?"`.
- [ ] Todos los casos de §3.2 pasan.

---

## 4. Feature C — `info <archivo>` debe ser concurrente

### 4.1 Problema

El comando `info <archivo>` itera secuencialmente sobre los entries (`cli.py:239-263`):

```python
for idx, entry in enumerate(result.entries, start=1):
    info_dict = fetch_metadata_cached(entry.url, cache=cache)
    ...
```

Para 50 tracks, esto toma ~100-150 s (sitios lentos como SoundCloud). Con concurrencia, ~30-50 s.

### 4.2 Solución

Refactorizar con `ThreadPoolExecutor` (mismo patrón que `download_all`), preservando el orden con pre-asignación de resultados.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

rows: list[tuple[str, str, str, str, str] | None] = [None] * len(result.entries)

def fetch_one(idx: int, entry: LinkEntry) -> tuple[int, tuple[str, str, str, str, str]]:
    try:
        info_dict = fetch_metadata_cached(entry.url, cache=cache)
        md = build_metadata(...)
        existing = _existing_path_for(entry.video_id, md.artist, md.title, idx, config)
        downloaded = "✓" if existing else "—"
        return idx, (str(idx), md.artist, md.title, _format_duration(info_dict.get("duration")), downloaded)
    except Exception as e:
        return idx, (str(idx), "?", entry.url[:40], "?", f"err: {e}")

with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
    futures = {executor.submit(fetch_one, idx, entry): idx for idx, entry in enumerate(result.entries, start=1)}
    for future in as_completed(futures):
        idx, row = future.result()
        rows[idx - 1] = row  # preservar orden

rows = [r for r in rows if r is not None]
```

### 4.3 Criterios de aceptación

- [ ] La tabla de `info <archivo>` muestra los mismos datos y orden que antes.
- [ ] El tiempo de ejecución para 50 entries es ~3x menor (con `concurrency=3`).
- [ ] Si una llamada falla, esa fila muestra `err: <mensaje>` y las demás se completan.
- [ ] El orden de la tabla coincide con el orden de `links.txt`.

---

## 5. Tests a agregar

**Archivo**: `tests/test_cli.py`

### Feature A — URL downloaded status (3 tests)

```python
def test_info_url_shows_downloaded_when_file_exists(tmp_path: Path) -> None:
    """info <URL> debe mostrar ✓ cuando el archivo ya está en output_dir."""

def test_info_url_shows_not_downloaded_when_file_missing(tmp_path: Path) -> None:
    """info <URL> debe mostrar — cuando el archivo no existe."""

def test_info_url_with_custom_template_without_track_number(tmp_path: Path) -> None:
    """Si el template no incluye {track_number}, igual debe detectar el archivo."""
```

### Feature B — Duration formatting (12 casos parametrizados)

```python
@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, "?"), (0, "?"),
        (59, "0:59"), (60, "1:00"), (213, "3:33"),
        (3599, "59:59"), (3600, "1:00:00"), (3661, "1:01:01"),
        (3930, "1:05:30"), (7325, "2:02:05"), (36000, "10:00:00"),
    ],
)
def test_format_duration(seconds: int | float | None, expected: str) -> None:
    """_format_duration maneja horas correctamente y preserva formato corto."""

def test_format_duration_accepts_float_seconds() -> None:
    """Floats se truncan a int antes de formatear."""
```

### Feature C — Concurrency (2 tests)

```python
def test_info_file_uses_concurrency(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """info <archivo> debe lanzar fetch_metadata_cached en paralelo."""

def test_info_file_preserves_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """La tabla de info debe estar en el orden de links.txt aunque las llamadas terminen desordenadas."""
```

**Total tests nuevos: 17**

---

## 6. Archivos a modificar

### 6.1 `src/yt_links_mp3/cli.py`

**Tres cambios:**

**B.1 — `_format_duration` (líneas 144-150):**
```diff
 def _format_duration(seconds: int | float | None) -> str:
-    """Formatea segundos a MM:SS."""
+    """Formatea segundos a M:SS o H:MM:SS según corresponda."""
     if not seconds:
         return "?"
     s = int(seconds)
-    m, sec = divmod(s, 60)
-    return f"{m}:{sec:02d}"
+    h, rem = divmod(s, 3600)
+    m, sec = divmod(rem, 60)
+    if h > 0:
+        return f"{h}:{m:02d}:{sec:02d}"
+    return f"{m}:{sec:02d}"
```

**A.1 — Rama URL del comando `info` (líneas 213-219):**
```diff
+        # Detectar si ya está descargado
+        video_id = raw_info.get("id", "?")
+        existing = _existing_path_for(
+            entry_video_id=video_id,
+            metadata_artist=md.artist,
+            metadata_title=md.title,
+            track_number=1,
+            config=config,
+        )
         click.echo(f"   ID:       {raw_info.get('id', '?')}")
+        if existing is not None:
+            click.echo(f"\n   ✓ Ya descargado: {existing.name}")
+        else:
+            click.echo(f"\n   — No descargado todavía")
+        click.echo()
```

**C.1 — Rama archivo del comando `info` (líneas 239-263):**
Reemplazar el loop `for idx, entry in enumerate(...)` por la versión con `ThreadPoolExecutor` de §4.2. Mantener el renderizado de tabla al final.

### 6.2 `tests/test_cli.py`

Agregar los 17 tests descritos en §5.

---

## 7. Verificación

```bash
# Feature B: verificar función directamente
python -c "from yt_links_mp3.cli import _format_duration; print(_format_duration(3930))"
# Debe imprimir: 1:05:30

# Feature A: smoke test con un video ya descargado y uno nuevo
yt-links-mp3 info "https://youtu.be/dQw4w9WgXcQ"

# Feature C: medir tiempo antes/después
time yt-links-mp3 info ~/Music/links.txt

# Suite completa
pytest tests/test_cli.py -v
pytest  # 125 + 17 = 142 pasando
```

---

## 8. Edge cases

### 8.1 Feature A — Template sin track number
`_existing_path_for` ya respeta `config.filename_template`. Si el template no incluye `{track_number}`, no se usa — no afecta.

### 8.2 Feature B — Duraciones negativas o NaN
`if not seconds` cubre ambos (`bool(0)` es False → `?`). Aceptable.

### 8.3 Feature C — Ctrl+C
Python's `ThreadPoolExecutor` no soporta cancelación cooperativa. `Ctrl+C` mata el proceso; los threads en background terminan cuando el proceso cierra. Aceptable para `info`.

### 8.4 Feature C — Orden en tabla
Pre-asignación `rows[idx - 1] = row` garantiza que aunque los futures completen fuera de orden, la tabla se muestra en el orden del archivo.

---

## 9. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Feature A: `_existing_path_for` falla con caracteres especiales | Baja | Bajo | Ya cubierto por `paths.sanitize` |
| Feature B: cambio en output rompe parsing de usuarios | Muy baja | Bajo | Output nunca fue formalmente estable |
| Feature C: orden de la tabla cambia por error | Baja | Medio | `test_info_file_preserves_order` cubre esto |
| Concurrency con `concurrency=1` cambia comportamiento | Muy baja | Bajo | Con `max_workers=1` el pool ejecuta secuencialmente |

---

## 10. Checklist de cierre

- [ ] Modificada `_format_duration` en `cli.py:144-150` (Feature B)
- [ ] Agregada detección de archivo existente en rama URL de `info` (Feature A)
- [ ] Refactorizado loop de `info <archivo>` con `ThreadPoolExecutor` (Feature C)
- [ ] Preservado el orden de la tabla con pre-asignación de rows (Feature C)
- [ ] Agregados 17 tests en `tests/test_cli.py`
- [ ] `pytest` → 142/142 pasando (125 + 17 nuevos)
- [ ] Smoke test manual de cada feature
- [ ] Commit con mensaje: `feat(cli): info command polish — URL status, H:MM:SS duration, concurrent file info`
- [ ] Push

---

## 11. Specs reemplazadas

Este spec reemplaza y consolida:

- `SPEC-004-format-duration-hours.md` — Feature B
- `SPEC-005-info-file-concurrent.md` — Feature C

(La Feature A era parte original de este spec, `SPEC-003-info-url-downloaded-status.md`.)
