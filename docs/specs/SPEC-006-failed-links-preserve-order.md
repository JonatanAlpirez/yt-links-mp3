# SPEC-006: Preservar orden original en `links.txt.failed`

| Campo | Valor |
|---|---|
| **ID** | SPEC-006 |
| **Título** | `links.txt.failed` se escribe en orden de completación (no de aparición), perdiendo el orden original del archivo |
| **Severidad** | 🟢 Baja (UX, no afecta correctness de descargas) |
| **Estado** | Draft → Ready for implementation |
| **Archivos afectados** | `src/yt_links_mp3/downloader.py`, `tests/test_downloader.py` (nuevos tests) |
| **Esfuerzo estimado** | 10–15 min |
| **Riesgo de regresión** | Bajo (solo cambia el orden de salida de `failed.txt`) |

---

## 1. Contexto

El archivo `links.txt.failed` se genera cuando una o más descargas fallan. El usuario lo usa para reintentar (`yt-links-mp3 download links.txt.failed`).

**Comportamiento actual** (`downloader.py:262-271`):

```python
def write_failed_links(results: list[DownloadResult], output_path: str) -> int:
    failed = [r for r in results if not r.success]
    if not failed:
        return 0
    lines = ["# Links fallidos - reintentá con: yt-links-mp3 download <este archivo>\n"]
    for r in failed:
        lines.append(f"{r.entry.url}    {r.entry.description or ''}\n")
    Path(output_path).write_text("".join(lines), encoding="utf-8")
    return len(failed)
```

El parámetro `results` viene de `download_all` (`downloader.py:250-259`):

```python
results: list[DownloadResult] = []
with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
    future_to_idx = {
        executor.submit(download_one, entry, config, idx): idx for idx, entry in indexed
    }
    for future in as_completed(future_to_idx):
        result = future.result()
        results.append(result)  # ← orden = orden de completación, NO orden original
```

`as_completed` yield a los futures en el orden en que terminan, **no en el orden en que fueron submitted**.

### 1.1 Por qué importa

Caso real:

```
links.txt (orden original):
  1. https://youtu.be/track-A      (lento, 30s)
  2. https://youtu.be/track-B      (rápido, 5s)         ← falla (privado)
  3. https://youtu.be/track-C      (rápido, 5s)         ← falla (404)
  4. https://youtu.be/track-D      (lento, 30s)
```

Con `as_completed`:
- A los 5s completan B y C (fallan).
- A los 30s completan A y D (éxito).
- `results = [B, C, A, D]` o `[C, B, A, D]` (no determinista por scheduling).

`failed.txt` actual:
```
track-B
track-C
```

(Orden arbitrario — **no coincide** con el orden del archivo original.)

`failed.txt` esperado:
```
track-B    (línea 2 del original)
track-C    (línea 3 del original)
```

(Orden preservado — más fácil de correlacionar con `links.txt` original.)

**Impacto**: cuando el usuario reintenta con `failed.txt`, el orden de descarga cambia. Si está debuggeando "qué falla en este archivo", comparar `failed.txt` con el original es molesto.

### 1.2 Severidad

Baja. No es un bug funcional — la descarga funciona, el reintento funciona. Es solo cosmético/organizacional.

---

## 2. Scope

### 2.1 Dentro de scope

- Modificar `download_all` o `write_failed_links` para preservar el orden original (por `entry.line_number`) al escribir `failed.txt`.
- Mantener el resto del output idéntico: header `# Links fallidos`, formato `<url>    <description>`.

### 2.2 Fuera de scope

- Cambiar el orden de ejecución de las descargas (sigue siendo concurrente).
- Cambiar el formato del `failed.txt` (líneas con `<url>    <description>`).
- Agregar timestamp o número de intento a cada línea del `failed.txt`.
- Reordenar los resultados que retorna `download_all` (el caller `cli.py:82-88` solo itera, no le importa el orden).

---

## 3. Solución propuesta

### 3.1 Decisión de diseño

**Elegido: ordenar `failed` por `entry.line_number` antes de escribir.**

Justificación:

| Alternativa | Ventaja | Desventaja |
|---|---|---|
| **Ordenar por `line_number`** (elegido) | Mínimo cambio, determinista, no afecta performance | Una sola pasada de sort (O(N log N)) |
| Ordenar en `download_all` antes de retornar | Una sola fuente de verdad | Cambia el contrato de `download_all`, puede romper callers existentes |
| Usar `entry.index` (track_number) en vez de `line_number` | Ya se calcula | `track_number` puede no ser igual a `line_number` si hay comentarios o líneas vacías — pero la dedupe preserva el orden de primera aparición, así que **en este proyecto son iguales** |

### 3.2 Implementación propuesta

**Opción A** (preferida): ordenar en `write_failed_links` (no toca `download_all`):

```python
def write_failed_links(results: list[DownloadResult], output_path: str) -> int:
    failed = [r for r in results if not r.success]
    if not failed:
        return 0
    # Preservar orden original del archivo de entrada
    failed.sort(key=lambda r: r.entry.line_number)
    lines = ["# Links fallidos - reintentá con: yt-links-mp3 download <este archivo>\n"]
    for r in failed:
        lines.append(f"{r.entry.url}    {r.entry.description or ''}\n")
    Path(output_path).write_text("".join(lines), encoding="utf-8")
    return len(failed)
```

**Opción B**: ordenar en `download_all` (cambio de contrato):

```python
def download_all(entries: list[LinkEntry], config: Config) -> list[DownloadResult]:
    # ... (código existente hasta el with ThreadPoolExecutor) ...
    results: list[DownloadResult] = []
    with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
        future_to_idx = {
            executor.submit(download_one, entry, config, idx): idx for idx, entry in indexed
        }
        for future in as_completed(future_to_idx):
            result = future.result()
            results.append(result)
    # NUEVO: ordenar por line_number para preservar orden del archivo original
    results.sort(key=lambda r: r.entry.line_number)
    return results
```

**Recomendación**: Opción A. Es más localizada, no cambia el contrato de `download_all`, y solo afecta `failed.txt` que es el caso de uso afectado.

---

## 4. Criterios de aceptación

### 4.1 Funcionales

- [ ] `links.txt.failed` contiene los links fallidos en el mismo orden en que aparecían en el archivo original.
- [ ] El orden es determinista: dos corridas con los mismos fallos producen el mismo `failed.txt`.
- [ ] El header `# Links fallidos - reintentá con: ...` se mantiene.
- [ ] El formato de cada línea (`<url>    <description>`) no cambia.

### 4.2 No regresión

- [ ] Si no hay fallos, no se crea el archivo (igual que antes).
- [ ] El comando `yt-links-mp3 download links.txt.failed` sigue funcionando (formato compatible).
- [ ] Los 125 tests existentes siguen pasando.
- [ ] El comando `download` principal sigue funcionando (no se tocó `download_all` en Opción A).

### 4.3 Tests a agregar

**Archivo a modificar**: `tests/test_downloader.py`

Agregar 3 tests:

```python
def test_write_failed_links_preserves_original_order(tmp_path: Path) -> None:
    """Los links fallidos deben escribirse en el orden del archivo original."""
    # Construir entries con line_numbers específicos
    e1 = LinkEntry(video_id="id1", url="https://youtu.be/id1", description=None, line_number=1, raw="id1")
    e2 = LinkEntry(video_id="id2", url="https://youtu.be/id2", description=None, line_number=2, raw="id2")
    e3 = LinkEntry(video_id="id3", url="https://youtu.be/id3", description=None, line_number=3, raw="id3")

    # Resultados en orden de completación (shuffled)
    results = [
        DownloadResult(entry=e3, success=False, output_path=None, error="err", skipped=False),  # terminó último
        DownloadResult(entry=e1, success=False, output_path=None, error="err", skipped=False),  # terminó primero
        DownloadResult(entry=e2, success=False, output_path=None, error="err", skipped=False),  # terminó segundo
    ]

    output = tmp_path / "failed.txt"
    write_failed_links(results, str(output))

    content = output.read_text(encoding="utf-8")
    lines = [l for l in content.splitlines() if not l.startswith("#") and l.strip()]

    # Debe estar en orden 1, 2, 3 (line_number)
    assert "id1" in lines[0]
    assert "id2" in lines[1]
    assert "id3" in lines[2]


def test_write_failed_links_skips_successful(tmp_path: Path) -> None:
    """Solo los links con success=False deben aparecer en failed.txt."""
    e1 = LinkEntry(video_id="id1", url="https://youtu.be/id1", description=None, line_number=1, raw="id1")
    e2 = LinkEntry(video_id="id2", url="https://youtu.be/id2", description=None, line_number=2, raw="id2")
    e3 = LinkEntry(video_id="id3", url="https://youtu.be/id3", description=None, line_number=3, raw="id3")

    results = [
        DownloadResult(entry=e1, success=True, output_path="/x.mp3", error=None, skipped=False),
        DownloadResult(entry=e2, success=False, output_path=None, error="err", skipped=False),
        DownloadResult(entry=e3, success=True, output_path="/y.mp3", error=None, skipped=True),
    ]

    output = tmp_path / "failed.txt"
    write_failed_links(results, str(output))

    content = output.read_text(encoding="utf-8")
    assert "id1" not in content
    assert "id2" in content
    assert "id3" not in content


def test_write_failed_links_no_file_when_empty(tmp_path: Path) -> None:
    """Si no hay fallos, no se crea el archivo."""
    e1 = LinkEntry(video_id="id1", url="https://youtu.be/id1", description=None, line_number=1, raw="id1")
    results = [
        DownloadResult(entry=e1, success=True, output_path="/x.mp3", error=None, skipped=False),
    ]

    output = tmp_path / "failed.txt"
    count = write_failed_links(results, str(output))

    assert count == 0
    assert not output.exists()
```

---

## 5. Archivos a modificar

### 5.1 `src/yt_links_mp3/downloader.py`

**Líneas 262-271** (función `write_failed_links`):

```diff
 def write_failed_links(results: list[DownloadResult], output_path: str) -> int:
     """Escribe los links fallidos a un archivo para reintentar. Devuelve cuántos escribió."""
     failed = [r for r in results if not r.success]
     if not failed:
         return 0
+    # Preservar orden original del archivo de entrada (no el orden de completación)
+    failed.sort(key=lambda r: r.entry.line_number)
     lines = ["# Links fallidos - reintentá con: yt-links-mp3 download <este archivo>\n"]
     for r in failed:
         lines.append(f"{r.entry.url}    {r.entry.description or ''}\n")
     Path(output_path).write_text("".join(lines), encoding="utf-8")
     return len(failed)
```

### 5.2 `tests/test_downloader.py`

Agregar los 3 tests descritos en §4.3.

---

## 6. Comandos de verificación

```bash
# 1. Setup: crear archivo con orden conocido
cat > /tmp/test_order.txt <<EOF
# Líneas en este orden: 1=track-A, 2=track-B (privado), 3=track-C
https://youtu.be/AAAAAAAAAAA
https://youtu.be/BBBBBBBBBBB
https://youtu.be/CCCCCCCCCCC
EOF

# 2. Forzar que algunos fallen (usando IDs privados/inexistentes)
yt-links-mp3 download /tmp/test_order.txt -o /tmp/test_out
cat /tmp/test_out/links.txt.failed
# Debe mostrar los fallidos en orden de aparición en el archivo original

# 3. Tests
pytest tests/test_downloader.py::test_write_failed_links_preserves_original_order -v
pytest tests/test_downloader.py::test_write_failed_links_skips_successful -v
pytest tests/test_downloader.py::test_write_failed_links_no_file_when_empty -v

# 4. Suite completa
pytest
```

---

## 7. Edge cases y consideraciones

### 7.1 ¿Por qué ordenar por `line_number` y no por `track_number`?

- `track_number` se calcula en `download_all:248` como `enumerate(entries) + 1`. Es igual a la posición del entry en la lista parseada.
- `line_number` se asigna en `linklist.py:126` como `enumerate(raw_text.splitlines(), start=1)` — la línea en el archivo original.
- **Diferencia**: si el archivo tiene líneas vacías o comentarios, `track_number` no coincide con `line_number`.

Ejemplo:

```
links.txt:
  1: # comentario       ← line 1, no entry
  2:                    ← line 2, vacío, no entry
  3: video-A            ← line 3, track 1
  4: video-B            ← line 4, track 2
```

- `track_number`: A=1, B=2
- `line_number`: A=3, B=4

Ambos ordenan igual (A antes que B). **Para el orden, da igual cuál se use**.

Pero `line_number` es más informativo si el usuario está debuggeando: "falló la línea 7 del archivo" es más útil que "falló el track 5".

**Recomendación**: usar `line_number` por consistencia con el resto del código (linklist.py y los mensajes de skip usan line_number).

### 7.2 ¿Estabilidad del sort?

Python's `sort` (Timsort) es estable. Si dos entries tienen el mismo `line_number` (no debería pasar), mantienen su orden relativo. Pero `line_number` debe ser único por entry en este proyecto (asignado por enumerate).

### 7.3 Performance

Sort de N elementos es O(N log N). Para N=100 es ~700 comparaciones — negligible. No es un cuello de botella.

### 7.4 ¿Afecta al comando `download <failed.txt>`?

No. El parser `parse_link_file` (`linklist.py:105-161`) acepta cualquier orden de URLs. El orden en `failed.txt` solo afecta la prioridad de descarga (cuál se intenta primero). Como el orden ahora es "orden original", es más predecible.

---

## 8. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Cambiar el orden rompe algún test que asume orden de completación | Baja | Bajo | Buscar tests que asuman orden — si existen, actualizar |
| `line_number` no es único en algún edge case | Muy baja | Bajo | Cada entry se asigna con `enumerate(start=1)` en `linklist.py:126` — únicos por construcción |
| Ordenar N=1000 entries toma tiempo perceptible | Muy baja | Nulo | O(N log N) para N=1000 es ~10000 ops — <1ms |

---

## 9. Checklist de cierre (para el implementador)

- [ ] Modificada `write_failed_links` en `downloader.py:262-271` con `failed.sort(key=lambda r: r.entry.line_number)`
- [ ] Agregados 3 tests en `tests/test_downloader.py`
- [ ] Correr `pytest` → 128/128 pasando (125 + 3 nuevos)
- [ ] Smoke test manual: forzar fallos con IDs privados, verificar orden de `failed.txt`
- [ ] Commit con mensaje: `fix(downloader): preserve original line order in links.txt.failed`
- [ ] Push

---

## 10. Open questions

1. **¿Vale la pena agregar el número de intento al `failed.txt`?** (ej: `track-X (intentos: 3)`) → **Decisión**: fuera de scope. El usuario puede ver `attempts` en el log si lo necesita.
2. **¿Deberíamos crear un `failed.txt` con timestamp para no pisar el anterior?** → **Decisión**: fuera de scope. El comportamiento actual (sobrescribir) es el documentado.
3. **¿Vale la pena hacer que el orden también aplique al resumen en consola (`✅ N descargados, ❌ M fallidos`)?** → **Decisión**: no aplica, el resumen es por conteo, no por lista.

---

## 11. Referencias

- Función actual: `downloader.py:262-271`.
- Por qué ocurre: `downloader.py:255` usa `as_completed`.
- Campo `line_number` en `LinkEntry`: `linklist.py:43` y asignación en `linklist.py:126`.
- Reporte de análisis post-Phase 5 (issue 🟢 Baja #5).