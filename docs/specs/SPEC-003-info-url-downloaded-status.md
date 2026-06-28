# SPEC-003: `info <URL>` debe mostrar estado "ya descargado"

| Campo | Valor |
|---|---|
| **ID** | SPEC-003 |
| **Título** | El comando `info <URL>` no muestra si el video ya está descargado, aunque el README promete el feature |
| **Severidad** | 🟡 Media (UX, inconsistencia entre comandos y docs) |
| **Estado** | Draft → Ready for implementation |
| **Archivos afectados** | `src/yt_links_mp3/cli.py` |
| **Esfuerzo estimado** | 10–15 min |
| **Riesgo de regresión** | Bajo (solo afecta la salida de `info`; no toca lógica de descarga) |

---

## 1. Contexto

El comando `info` tiene dos modos según el argumento:

| Argumento | Comportamiento actual | Estado "Descargado" |
|---|---|---|
| `info <URL>` (rama `_is_url_like=True`) | Muestra título, artista, duración, ID | ❌ **No se muestra** |
| `info <archivo.txt>` | Muestra tabla con N, Artista, Título, Duración, **Descargado** | ✅ Se muestra ✓/— |

El README (`README.md:339`) promete:

> Muestra título, artista, duración y si ya está descargado, sin tocar disco.

La promesa se cumple solo para la rama de archivo. Para una URL o ID suelto, el usuario no puede saber si ese video específico ya fue descargado a `output_dir`.

### 1.1 Por qué importa

Caso de uso real:

```bash
# El usuario está decidiendo si descargar algo nuevo
yt-links-mp3 info "https://youtu.be/dQw4w9WgXcQ"
# → Hoy: solo metadata
# → Deseado: metadata + indicador "✓ ya descargado: 01 - Rick Astley - Never Gonna Give You Up.mp3"
```

Sin este feature, el usuario tiene que ir a la carpeta `output_dir` y buscar manualmente por título aproximado.

### 1.2 Reproducción

```bash
$ yt-links-mp3 info "https://youtu.be/dQw4w9WgXcQ"
# (después de haber descargado el track)

🎬 Never Gonna Give You Up
   Canal:    Rick Astley
   Artista:  Rick Astley
   Titulo:   Never Gonna Give You Up
   Duracion: 3:33
   ID:       dQw4w9WgXcQ

# → No hay indicación de que ya está descargado.
```

---

## 2. Scope

### 2.1 Dentro de scope

- Modificar la rama URL del comando `info` (cli.py:193-219) para detectar si el track ya está descargado y mostrar el indicador correspondiente.
- Reusar la función helper `_existing_path_for` (cli.py:153-177) que ya existe y hace exactamente esto para la rama de archivo.
- Mostrar el path del archivo existente si lo hay.

### 2.2 Fuera de scope

- Cambiar el formato de salida de `info <archivo>` (la tabla está bien).
- Agregar búsqueda fuzzy por título (overkill — el `video_id` es match exacto).
- Agregar opción para borrar el archivo existente desde `info` (fuera del scope del comando).
- Mostrar estadísticas (cuántos MB tiene el archivo, bitrate real, etc.).

---

## 3. Solución propuesta

### 3.1 Decisión de diseño

**Elegido: reusar `_existing_path_for` en la rama URL con `track_number=1`**.

Justificación:

| Alternativa | Ventaja | Desventaja |
|---|---|---|
| **Reusar `_existing_path_for`** (elegido) | DRY, una sola implementación | Asume `track_number=1` que puede no ser el real |
| Crear una variante sin track_number | Más semántico | Duplica lógica |
| Buscar por glob `*.mp3` con el título aproximado | No necesita metadata | Fuzzy match, falsos positivos |

El `track_number=1` es aceptable porque el filename solo incluye el track number cuando el template es el default (`{track_number:02d} - {artist} - {title}.{ext}`). Si el usuario customizó el template para no incluir track_number, no afecta nada.

### 3.2 Cambio de output

**Antes** (cli.py:213-219):

```
🎬 Never Gonna Give You Up
   Canal:    Rick Astley
   Artista:  Rick Astley
   Titulo:   Never Gonna Give You Up
   Duracion: 3:33
   ID:       dQw4w9WgXcQ
```

**Después**:

```
🎬 Never Gonna Give You Up
   Canal:    Rick Astley
   Artista:  Rick Astley
   Titulo:   Never Gonna Give You Up
   Duracion: 3:33
   ID:       dQw4w9WgXcQ

   ✓ Ya descargado: 01 - Rick Astley - Never Gonna Give You Up.mp3
```

O, si NO está descargado:

```
🎬 Never Gonna Give You Up
   Canal:    Rick Astley
   Artista:  Rick Astley
   Titulo:   Never Gonna Give You Up
   Duracion: 3:33
   ID:       dQw4w9WgXcQ

   — No descargado todavía
```

### 3.3 Patrón de implementación

En `cli.py`, dentro de la rama `_is_url_like` del comando `info`, después de construir `md`:

```python
# Detectar si ya está descargado (reusar helper)
existing = _existing_path_for(
    entry_video_id=raw_info.get("id", "?"),
    metadata_artist=md.artist,
    metadata_title=md.title,
    track_number=1,  # placeholder; no se usa si el template no incluye {track_number}
    config=config,
)
click.echo(f"   ID:       {raw_info.get('id', '?')}")
if existing is not None:
    click.echo(f"\n   ✓ Ya descargado: {existing.name}")
else:
    click.echo(f"\n   — No descargado todavía")
click.echo()
```

---

## 4. Criterios de aceptación

### 4.1 Funcionales

- [ ] `info <URL>` muestra `✓ Ya descargado: <filename>` cuando el archivo existe en `output_dir`.
- [ ] `info <URL>` muestra `— No descargado todavía` cuando el archivo NO existe.
- [ ] `info <ID de 11 chars>` tiene el mismo comportamiento (mismo código path).
- [ ] El nombre de archivo detectado coincide exactamente con el filename que generaría `download` con los mismos metadata (round-trip).
- [ ] Si el template custom del usuario no incluye `{track_number}`, sigue funcionando (no rompe).

### 4.2 No regresión

- [ ] `info <archivo.txt>` mantiene el comportamiento actual (tabla con columna "Descargado").
- [ ] El formato del output de metadata (líneas `Canal:`, `Artista:`, `Titulo:`, `Duracion:`, `ID:`) no cambia.
- [ ] Los 125 tests existentes siguen pasando.
- [ ] No se agrega dependencia nueva.

### 4.3 Tests a agregar

**Archivo a modificar**: `tests/test_cli.py`

Agregar 3 tests:

```python
def test_info_url_shows_downloaded_when_file_exists(tmp_path: Path) -> None:
    """info <URL> debe mostrar ✓ cuando el archivo ya está en output_dir."""
    # Setup: crear archivo "fake.mp3" en output_dir con el nombre esperado
    config = Config.load()
    config.output_dir = tmp_path
    # ... construir el filename esperado usando metadata ...
    # Mockear fetch_metadata_cached para retornar info controlada
    # Invocar info y verificar que el output contiene "✓ Ya descargado"
    ...


def test_info_url_shows_not_downloaded_when_file_missing(tmp_path: Path) -> None:
    """info <URL> debe mostrar — cuando el archivo no existe."""
    config = Config.load()
    config.output_dir = tmp_path
    # Mockear fetch_metadata_cached
    # Invocar info y verificar que el output contiene "— No descargado"
    ...


def test_info_url_with_custom_template_without_track_number(tmp_path: Path) -> None:
    """Si el template no incluye {track_number}, igual debe detectar el archivo."""
    config = Config.load()
    config.filename_template = "{artist} - {title}.{ext}"
    config.output_dir = tmp_path
    # ... crear el archivo con el nombre simple ...
    # Invocar info y verificar ✓
    ...
```

(Los tests usarán `click.testing.CliRunner` para invocar el comando y capturar el output, mocking `fetch_metadata_cached` con `monkeypatch` o `unittest.mock`.)

---

## 5. Archivos a modificar

### 5.1 `src/yt_links_mp3/cli.py`

**Líneas 213-219** (rama URL del comando `info`):

```diff
         click.echo(f"\n🎬 {raw_info.get('title', '?')}")
         click.echo(f"   Canal:    {raw_info.get('uploader') or raw_info.get('channel') or '?'}")
         click.echo(f"   Artista:  {md.artist}")
         click.echo(f"   Titulo:   {md.title}")
         click.echo(f"   Duracion: {_format_duration(raw_info.get('duration'))}")
         click.echo(f"   ID:       {raw_info.get('id', '?')}")
+
+        # Detectar si ya está descargado
+        video_id = raw_info.get("id", "?")
+        existing = _existing_path_for(
+            entry_video_id=video_id,
+            metadata_artist=md.artist,
+            metadata_title=md.title,
+            track_number=1,
+            config=config,
+        )
+        click.echo()
+        if existing is not None:
+            click.echo(f"   ✓ Ya descargado: {existing.name}")
+        else:
+            click.echo(f"   — No descargado todavía")
+
         click.echo()
```

### 5.2 `tests/test_cli.py`

Agregar los 3 tests descritos en §4.3.

---

## 6. Comandos de verificación

```bash
# 1. Setup: descargar algo
yt-links-mp3 download ~/Music/links.txt -o /tmp/test

# 2. Verificar info <URL> cuando ya está descargado
yt-links-mp3 info "https://youtu.be/<id_descargado>"
# Debe mostrar: ✓ Ya descargado: NN - Artist - Title.mp3

# 3. Verificar info <URL> cuando NO está descargado
yt-links-mp3 info "https://youtu.be/<id_no_descargado>"
# Debe mostrar: — No descargado todavía

# 4. Verificar info <archivo.txt> sigue funcionando (no regresión)
yt-links-mp3 info ~/Music/links.txt
# Debe mostrar la tabla como antes, sin cambios

# 5. Tests
pytest tests/test_cli.py -v
pytest  # todos los 125 + 3 nuevos = 128
```

---

## 7. Edge cases y consideraciones

### 7.1 ¿Qué pasa si el usuario customizó `filename_template`?

`_existing_path_for` ya respeta `config.filename_template`. Si el template es `{artist} - {title}.{ext}` (sin `{track_number}`), el filename detectado es el correcto.

El `track_number=1` pasado al helper solo se usa si el template incluye `{track_number}`. Si el template custom no lo incluye, no se usa → no afecta.

### 7.2 ¿Qué pasa si la metadata de YouTube cambia entre `download` y `info`?

El round-trip puede romperse (ej: el canal cambió de nombre). En ese caso, `info` mostrará "— No descargado todavía" aunque el archivo exista pero con nombre ligeramente diferente.

**Mitigación aceptable**: el archivo con nombre exacto existe → "✓"; si no → "—". El usuario puede hacer `find ~/Music/Downloads -iname "*rick astley*"` para buscar manualmente.

**Mitigación mejor (futuro, fuera de scope)**: búsqueda fuzzy por título aproximado con `difflib.SequenceMatcher` o similar.

### 7.3 ¿Multi-sitio?

`_existing_path_for` funciona con cualquier `video_id` (YouTube ID o URL completa para otros sitios). Para un `info https://soundcloud.com/artist/track`, la detección de descargado funciona igual.

### 7.4 ¿Cache miss vs cache hit?

No afecta: `fetch_metadata_cached` se llama antes, y `_existing_path_for` solo lee del filesystem. La lógica es independiente.

### 7.5 ¿Performance?

`_existing_path_for` hace un `target.exists()` (un stat call) — O(1). Sin impacto.

---

## 8. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| `_existing_path_for` falla con metadata que tiene caracteres especiales en el título | Baja | Bajo | Ya cubierto por `paths.sanitize` — `_existing_path_for` lo llama internamente vía `build_filename` |
| Round-trip roto por cambios en metadata de YouTube | Baja | Bajo | El feature degrada gracefully: muestra "—" en vez de crashear |
| `track_number=1` produce filename incorrecto si el template incluye `{track_number}` y el track fue descargado con otro número | Baja | Bajo (mismo problema de round-trip) | El usuario ve "—" y entiende que debe buscar manualmente |
| Tests flaky por filesystem state | Baja | Bajo | Usar `tmp_path` fixture de pytest en los tests nuevos |

---

## 9. Checklist de cierre (para el implementador)

- [ ] Modificado `cli.py` líneas 213-219 con detección de archivo existente
- [ ] Importado `_existing_path_for` ya está arriba del archivo (verificar)
- [ ] Agregados 3 tests en `tests/test_cli.py` con `tmp_path`
- [ ] Correr `pytest` → 128/128 pasando (125 + 3 nuevos)
- [ ] Smoke test manual con `info <URL>` de algo ya descargado y algo no descargado
- [ ] Commit con mensaje: `feat(cli): show 'already downloaded' status in info <URL>`
- [ ] Push

---

## 10. Open questions

1. **¿Deberíamos también mostrar el tamaño del archivo (`ls -lh` style)?** → **Decisión**: fuera de scope, agregar más info complica el output. Si el usuario quiere detalles, usa `ls`.
2. **¿Deberíamos abrir el archivo con el player default si ya está descargado?** → **Decisión**: no, ese es el job del file manager, no del CLI.
3. **¿Vale la pena agregar un flag `--check-only` que solo retorne exit code 0/1 según existencia?** → **Decisión**: fuera de scope. Si se necesita, en un spec separado.

---

## 11. Referencias

- Reporte de análisis post-Phase 5 (issue 🟡 Media #2).
- Helper `_existing_path_for`: `cli.py:153-177`.
- Output actual del comando `info`: `cli.py:213-219`.
- README.md:339 promesa del feature.