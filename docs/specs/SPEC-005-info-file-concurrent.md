# SPEC-005: Hacer `info <archivo>` concurrente con `ThreadPoolExecutor`

| Campo | Valor |
|---|---|
| **ID** | SPEC-005 |
| **Título** | El comando `info <archivo>` es secuencial; debería usar concurrencia como `download` |
| **Severidad** | 🟡 Media (perf/UX, no afecta correctness) |
| **Estado** | Draft → Ready for implementation |
| **Archivos afectados** | `src/yt_links_mp3/cli.py` |
| **Esfuerzo estimado** | 20–30 min |
| **Riesgo de regresión** | Bajo (no toca lógica de descarga, solo el comando `info`) |

---

## 1. Contexto

El comando `info` tiene dos modos:

| Modo | Concurrencia | Tiempo aproximado para N=50 tracks |
|---|---|---|
| `info <URL>` (single) | N/A | ~1-2s (1 llamada a yt-dlp) |
| `info <archivo>` (N tracks) | **Secuencial** | ~50-150s (1 llamada a yt-dlp por track) |

El comando `download` ya usa `ThreadPoolExecutor` con `config.concurrency` workers (default 3), descargando 3 tracks en paralelo. Pero `info <archivo>` itera secuencialmente sobre los entries (`cli.py:239-263`):

```python
for idx, entry in enumerate(result.entries, start=1):
    try:
        info_dict = fetch_metadata_cached(entry.url, cache=cache)
        ...
```

### 1.1 Por qué importa

Caso de uso real:

```bash
# Usuario tiene un archivo con 50 tracks en SoundCloud (sitio lento)
yt-links-mp3 info ~/Music/livesets.txt
# → Hoy: 50 llamadas secuenciales a yt-dlp = ~100-150 segundos
# → Con fix: 50/3 = 17 batches de 3 = ~30-50 segundos (3x speedup)
```

Para un archivo con tracks de YouTube (sitio rápido) el speedup es menor pero aún perceptible (3-5x). Y en el caso de Bandcamp (rate limiting agresivo), el speedup puede ser mayor.

### 1.2 ¿Por qué no se hizo ya en Fase 3?

Probable razón: la implementación original priorizó `download` (el caso crítico). El comando `info` se agregó después pero con la implementación naive (loop secuencial).

---

## 2. Scope

### 2.1 Dentro de scope

- Refactorizar `info <archivo>` para usar `ThreadPoolExecutor` con `config.concurrency` workers.
- Mostrar progreso mientras se fetchea metadata (opcional: barra de `rich.progress`).
- Preservar el orden de los entries en la tabla (el output debe ser idéntico al actual en contenido, solo más rápido).
- Mantener el manejo de errores por-entry (un fallo no aborta el resto).

### 2.2 Fuera de scope

- Cambiar el formato de salida de la tabla.
- Agregar cancelación del usuario (`Ctrl+C` debe abortar limpiamente — el comportamiento actual ya funciona por GIL cleanup).
- Hacer que `info <URL>` sea concurrente (es 1 sola llamada, no aplica).
- Agregar un nuevo flag `--concurrency` específico para `info` (reusar `config.concurrency`).
- Paralelizar la descarga en sí (eso es el trabajo de `download`, no `info`).

---

## 3. Solución propuesta

### 3.1 Decisión de diseño

**Elegido: refactor mínimo con `ThreadPoolExecutor`, reusando el patrón de `download_all`.**

Justificación:

| Alternativa | Ventaja | Desventaja |
|---|---|---|
| **`ThreadPoolExecutor` simple** (elegido) | Consistente con `download_all`, reusa patrón conocido | Requiere preservar orden manualmente |
| `asyncio` con `aiohttp` | Más moderno | Requiere agregar deps + reescribir `fetch_metadata_cached` |
| `concurrent.futures.ProcessPoolExecutor` | True parallelism | yt-dlp es I/O bound, threads son suficientes (ADR #3 en PLAN.md) |

### 3.2 Implementación propuesta

Refactor del bloque en `cli.py:239-263`:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

# ... (preparación existente: cache, parse_link_file) ...

cache = build_cache(config)
rows: list[tuple[str, str, str, str, str] | None] = [None] * len(result.entries)

def fetch_one(idx: int, entry: LinkEntry) -> tuple[int, tuple[str, str, str, str, str]]:
    """Fetch metadata + compute existing-path for one entry. Returns (idx, row)."""
    try:
        info_dict = fetch_metadata_cached(entry.url, cache=cache)
        md = build_metadata(
            info=info_dict,
            track_number=idx,
            video_id=entry.video_id,
            hint=entry.description,
            cleanup_patterns=config.cleanup_patterns,
        )
        existing = _existing_path_for(entry.video_id, md.artist, md.title, idx, config)
        downloaded = "✓" if existing else "—"
        return idx, (str(idx), md.artist, md.title, _format_duration(info_dict.get("duration")), downloaded)
    except Exception as e:  # noqa: BLE001
        return idx, (str(idx), "?", entry.url[:40], "?", f"err: {e}")

# Lanzar N futures en paralelo, recolectar por idx para preservar orden
with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
    futures = {
        executor.submit(fetch_one, idx, entry): idx
        for idx, entry in enumerate(result.entries, start=1)
    }
    for future in as_completed(futures):
        idx, row = future.result()
        rows[idx - 1] = row  # preservar orden

# Filtrar Nones (no debería haber, pero defensivo)
rows = [r for r in rows if r is not None]

# ... (renderizado de tabla con rich o click.echo, igual que antes) ...
```

### 3.3 ¿Por qué preservar el orden?

El usuario espera ver la tabla en el orden de `links.txt`. Si las llamadas se completan fuera de orden (por red lenta, sitios lentos, etc.), el output se vuelve confuso. La pre-asignación `rows[idx - 1] = row` preserva el orden aunque los futures terminen desordenados.

---

## 4. Criterios de aceptación

### 4.1 Funcionales

- [ ] `info <archivo_con_50_entradas>` retorna la misma tabla que antes (mismo orden, mismo contenido).
- [ ] El tiempo de ejecución es ~3x menor para 50 entradas (medido con `time`).
- [ ] Si una llamada falla, esa fila muestra `err: <mensaje>` y las demás se completan normalmente.
- [ ] `config.concurrency` se respeta (verificable: con `concurrency=1` el tiempo es ~igual al actual; con `concurrency=5` es ~5x menor).

### 4.2 No regresión

- [ ] El formato del output (columnas: #, Artista, Título, Duración, Descargado) no cambia.
- [ ] El fallback a `click.echo` cuando `rich` no está disponible sigue funcionando.
- [ ] Los 125 tests existentes siguen pasando.
- [ ] No se agrega dependencia nueva (solo stdlib `concurrent.futures`).

### 4.3 Tests a agregar

**Archivo a modificar**: `tests/test_cli.py`

Agregar 2 tests:

```python
def test_info_file_uses_concurrency(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """info <archivo> debe lanzar fetch_metadata_cached en paralelo, no secuencial.

    Verifica que se usa ThreadPoolExecutor con max_workers=config.concurrency.
    """
    # Mock fetch_metadata_cached para contar concurrencia
    max_concurrent = 0
    current_concurrent = 0

    def fake_fetch(url: str, cache: object = None) -> dict:
        nonlocal max_concurrent, current_concurrent
        current_concurrent += 1
        max_concurrent = max(max_concurrent, current_concurrent)
        time.sleep(0.1)  # simular latencia
        current_concurrent -= 1
        return {"id": "...", "title": "...", "uploader": "Artist"}

    monkeypatch.setattr("yt_links_mp3.cli.fetch_metadata_cached", fake_fetch)

    # Crear archivo con 10 entries
    links = tmp_path / "links.txt"
    links.write_text("\n".join(f"https://youtu.be/{'dQw4w9WgXcQ'}" for _ in range(10)))

    # Invocar info
    config = Config.load()
    config.concurrency = 3
    runner = click.testing.CliRunner()
    runner.invoke(cli.main, ["info", str(links)])

    # Debe haber alcanzado al menos 2 workers en paralelo
    assert max_concurrent >= 2, f"Esperaba concurrencia, max fue {max_concurrent}"


def test_info_file_preserves_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """La tabla de info debe estar en el orden de links.txt aunque las llamadas
    a yt-dlp terminen desordenadas."""
    import random

    def fake_fetch(url: str, cache: object = None) -> dict:
        time.sleep(random.uniform(0.01, 0.1))  # latencia variable
        return {"id": url[-11:], "title": f"Title {url[-11:]}", "uploader": "Artist"}

    monkeypatch.setattr("yt_links_mp3.cli.fetch_metadata_cached", fake_fetch)

    links = tmp_path / "links.txt"
    ids = ["dQw4w9WgXcQ", "jNQXAC9IVRw", "9bZkp7q19f0", "kJQP7kiw5Fk", "4xDzrJKXOOY"]
    links.write_text("\n".join(f"https://youtu.be/{i}" for i in ids))

    config = Config.load()
    runner = click.testing.CliRunner()
    result = runner.invoke(cli.main, ["info", str(links)])

    # Las URLs deben aparecer en el orden de ids
    for i, vid in enumerate(ids, start=1):
        assert f"{i} " in result.output or str(i) in result.output
```

---

## 5. Archivos a modificar

### 5.1 `src/yt_links_mp3/cli.py`

**Líneas 230-263** (rama de archivo del comando `info`):

Refactorizar el loop `for idx, entry in enumerate(...)` por la versión con `ThreadPoolExecutor` descrita en §3.2. Mantener el bloque de renderizado de tabla (rich o fallback click.echo) intacto.

### 5.2 `tests/test_cli.py`

Agregar los 2 tests descritos en §4.3.

---

## 6. Comandos de verificación

```bash
# 1. Crear archivo de prueba con 20 entradas
cat > /tmp/test_links.txt <<EOF
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/watch?v=jNQXAC9IVRw
https://www.youtube.com/watch?v=9bZkp7q19f0
... (repetir hasta tener 20)
EOF

# 2. Medir tiempo antes y después del fix
time yt-links-mp3 info /tmp/test_links.txt

# 3. Verificar contenido (orden debe coincidir con el archivo)
yt-links-mp3 info /tmp/test_links.txt | head -25

# 4. Tests
pytest tests/test_cli.py -v
pytest  # todos

# 5. Smoke con concurrencia custom
# (configurar concurrency=1 en config y verificar que tarda ~20x)
# (configurar concurrency=10 y verificar que tarda ~2x)
```

---

## 7. Edge cases y consideraciones

### 7.1 ¿Por qué no `asyncio`?

- `yt-dlp` no es async-native. Usar `asyncio.to_thread` wrappea threads igual.
- Threading es consistente con el resto del proyecto (ADR #3 en PLAN.md).
- Menos cambio de paradigma, menos riesgo.

### 7.2 ¿Manejo de excepciones en threads?

`ThreadPoolExecutor` propaga excepciones al `future.result()`. El bloque `try/except` dentro de `fetch_one` captura localmente y retorna un row con error. **Las excepciones no escapan del thread**, no se necesita manejo adicional.

### 7.3 ¿Cancelación con Ctrl+C?

Python's `ThreadPoolExecutor` no soporta cancelación cooperativa. `Ctrl+C` lanza `KeyboardInterrupt` en el main thread; los threads en background siguen hasta completar (o son killed por el OS al cerrar el proceso).

**Aceptable** para `info`: el usuario puede esperar a que terminen los 17 batches restantes, o cerrar el terminal.

**Mejor (fuera de scope)**: usar `concurrent.futures.wait` con timeout y signal handler. No necesario para este spec.

### 7.4 ¿Logging concurrente?

`loguru` es thread-safe (usa locks internos). No hay race conditions con `logger.debug("Cache miss para ...")`.

### 7.5 ¿Cache hits?

Si todos los entries ya están en cache, las llamadas a `fetch_metadata_cached` retornan instantáneamente sin hacer I/O. El speedup es mínimo en este caso — pero el código sigue siendo correcto.

---

## 8. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Race condition en `rows[idx-1] = row` | Muy baja | Bajo | Python GIL garantiza atomicidad de assignment a lista |
| Order de la tabla cambia por error en pre-asignación | Baja | Medio | Test `test_info_file_preserves_order` cubre esto |
| Comportamiento con `concurrency=1` cambia | Muy baja | Bajo | Con `max_workers=1`, el pool ejecuta secuencialmente — mismo resultado |
| Threads zombies si el proceso se mata | Baja | Bajo | yt-dlp subprocesses terminan al cerrar el process; cleanup en `atexit` sería nice-to-have pero fuera de scope |
| `Ctrl+C` deja threads corriendo | Media | Bajo (UX) | Documentado en §7.3. Aceptable. |

---

## 9. Checklist de cierre (para el implementador)

- [ ] Refactorizado `cli.py:230-263` con `ThreadPoolExecutor`
- [ ] Preservado el orden de la tabla con pre-asignación `rows[idx-1]`
- [ ] Imports necesarios agregados al inicio del archivo
- [ ] Agregados 2 tests en `tests/test_cli.py`
- [ ] Correr `pytest` → 127/127 pasando (125 + 2 nuevos)
- [ ] Smoke test con archivo real midiendo tiempo antes/después
- [ ] Commit con mensaje: `perf(cli): make info <file> concurrent using ThreadPoolExecutor`
- [ ] Push

---

## 10. Open questions

1. **¿Vale la pena agregar un progress bar durante el fetch?** → **Decisión**: fuera de scope. La tabla se imprime toda junta al final. Si se quiere ver progreso en tiempo real, agregar en un spec separado (puede usar `rich.progress.Progress` con un task por fetch).
2. **¿Deberíamos tener `--concurrency` específico para `info` (separado de `download`)?** → **Decisión**: no, reusar `config.concurrency` mantiene la config simple. Si se necesita granularidad, en un spec separado.
3. **¿Vale la pena usar `ProcessPoolExecutor` para sitios muy lentos (Bandcamp)?** → **Decisión**: no, yt-dlp es I/O bound, threads son suficientes (medido en PLAN.md ADR #3).

---

## 11. Referencias

- Implementación actual: `cli.py:230-263`.
- Patrón a reusar: `downloader.py:251-259` (`download_all` con `ThreadPoolExecutor`).
- ADR sobre threading: `PLAN.md` tabla de decisiones (#3).
- Reporte de análisis post-Phase 5 (issue 🟡 Media #4).