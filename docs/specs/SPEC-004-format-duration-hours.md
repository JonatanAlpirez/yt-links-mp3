# SPEC-004: `_format_duration` debe manejar horas correctamente

| Campo | Valor |
|---|---|
| **ID** | SPEC-004 |
| **Título** | `_format_duration` retorna formato incorrecto para videos de más de 1 hora (devuelve `MM:SS` en vez de `H:MM:SS`) |
| **Severidad** | 🟡 Media (bug visible, afecta caso de uso real de lives/mixes/podcasts) |
| **Estado** | Draft → Ready for implementation |
| **Archivos afectados** | `src/yt_links_mp3/cli.py`, `tests/test_cli.py` (nuevos tests) |
| **Esfuerzo estimado** | 10–15 min |
| **Riesgo de regresión** | Bajo (función pura, sin I/O, fácil de testear) |

---

## 1. Contexto

La función `_format_duration` (`cli.py:144-150`) formatea una duración en segundos a un string `M:SS`:

```python
def _format_duration(seconds: int | float | None) -> str:
    """Formatea segundos a MM:SS."""
    if not seconds:
        return "?"
    s = int(seconds)
    m, sec = divmod(s, 60)
    return f"{m}:{sec:02d}"
```

**Bug**: para duraciones ≥ 3600 segundos (1 hora), el cálculo de minutos incluye las horas implícitamente, produciendo resultados visualmente incorrectos.

### 1.1 Reproducción

```python
>>> _format_duration(65 * 60 + 30)  # 1h 5m 30s
'65:30'   # ← Incorrecto. Debería ser '1:05:30'
```

Casos reales afectados:

| Contenido | Duración | Salida actual | Salida esperada |
|---|---|---|---|
| Live set de DJ (Boiler Room, etc.) | 1h 30m | `90:00` | `1:30:00` |
| Podcast extraído de YouTube | 2h 15m | `135:00` | `2:15:00` |
| Mix largo de SoundCloud | 3h 45m 20s | `225:20` | `3:45:20` |
| Video normal (≤ 1h) | 3:33 (213s) | `3:33` | `3:33` (no cambia) |

El propio `PLAN.md:109` usa como ejemplo un live set de Boiler Room — el bug se manifestaría con exactamente ese caso de uso documentado.

### 1.2 Impacto

- **UX**: lectura confusa para contenido largo.
- **Funcional específico**: la salida del comando `info <archivo>` muestra esta columna ("Duración") — todos los archivos largos en una tabla aparecen con números de 3 dígitos en minutos, sin indicar que son horas.
- **Severidad real**: media. No rompe nada, solo es cosmetic. Pero el fix es trivial.

---

## 2. Scope

### 2.1 Dentro de scope

- Modificar `_format_duration` para retornar `H:MM:SS` cuando la duración es ≥ 1 hora, manteniendo `M:SS` para duraciones menores.
- Agregar tests de regresión que cubran: 0s, 59s, 60s, 3599s, 3600s, 7325s (2h 2m 5s).
- Actualizar el docstring de la función.

### 2.2 Fuera de scope

- Cambiar el formato a `HH:MM:SS` con cero-padding para horas (ej: `01:05:30` en vez de `1:05:30`). Decisión de diseño: omitir el zero-padding de horas porque las horas típicamente son 1-3 dígitos y el `0:` inicial es ruido. Ver §3.3.
- Internacionalización (i18n) del separador. Siempre `:`.
- Manejar duraciones negativas o NaN (no son entradas válidas en este contexto).
- Migrar la lógica a un módulo separado (utils). Hoy vive en `cli.py` porque es un helper cosmético del comando `info`. Si se reusa en otros lados en el futuro, mover a `utils.py`.

---

## 3. Solución propuesta

### 3.1 Decisión de diseño

**Elegido: formato adaptativo `H:MM:SS` (≥ 1h) o `M:SS` (< 1h).**

Justificación:

| Alternativa | Ventaja | Desventaja |
|---|---|---|
| **`H:MM:SS` / `M:SS` adaptativo** (elegido) | Consistente con el resto del CLI (no padding en `{track_number}`) | Más lógica condicional |
| Siempre `H:MM:SS` con cero-padding (`HH:MM:SS`) | Uniforme, fácil de parsear | Padding de horas es raro (3:33 → 0:03:33) |
| Usar `datetime.timedelta` | Stdlib, maneja todo | Output verbose: `1:05:30.000000` o requiere formateo custom |

### 3.2 Implementación propuesta

```python
def _format_duration(seconds: int | float | None) -> str:
    """Formatea segundos a M:SS o H:MM:SS según corresponda.

    Ejemplos:
        213         → '3:33'
        3599        → '59:59'
        3600        → '1:00:00'
        3930 (1h 5m 30s) → '1:05:30'
        None o 0    → '?'
    """
    if not seconds:
        return "?"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"
```

### 3.3 Casos de prueba

| Input | Output esperado |
|---|---|
| `None` | `?` |
| `0` | `?` |
| `59` | `0:59` |
| `60` | `1:00` |
| `213` | `3:33` |
| `3599` | `59:59` |
| `3600` | `1:00:00` |
| `3661` (1h 1m 1s) | `1:01:01` |
| `3930` (1h 5m 30s) | `1:05:30` |
| `7325` (2h 2m 5s) | `2:02:05` |
| `36000` (10h) | `10:00:00` |

---

## 4. Criterios de aceptación

### 4.1 Funcionales

- [ ] `_format_duration(3930)` retorna `"1:05:30"` (no `"65:30"`).
- [ ] `_format_duration(213)` retorna `"3:33"` (sin cambio para videos < 1h).
- [ ] `_format_duration(None)` retorna `"?"` (no cambia).
- [ ] `_format_duration(0)` retorna `"?"` (no cambia).
- [ ] Todos los casos de §3.3 pasan.

### 4.2 No regresión

- [ ] El comando `info <URL>` sigue mostrando la columna "Duracion" con el formato correcto.
- [ ] El comando `info <archivo>` sigue mostrando la columna "Duracion" en la tabla.
- [ ] Los 125 tests existentes siguen pasando.
- [ ] No se agrega dependencia nueva.

### 4.3 Tests a agregar

**Archivo a modificar**: `tests/test_cli.py`

Agregar tests parametrizados:

```python
import pytest
from yt_links_mp3.cli import _format_duration


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, "?"),
        (0, "?"),
        (59, "0:59"),
        (60, "1:00"),
        (213, "3:33"),
        (3599, "59:59"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
        (3930, "1:05:30"),
        (7325, "2:02:05"),
        (36000, "10:00:00"),
    ],
)
def test_format_duration(seconds: int | float | None, expected: str) -> None:
    """_format_duration maneja horas correctamente y preserva formato corto."""
    assert _format_duration(seconds) == expected
```

Adicionalmente, un test con `float` para confirmar el `int()` cast:

```python
def test_format_duration_accepts_float_seconds() -> None:
    """Floats se truncan a int antes de formatear."""
    assert _format_duration(213.7) == "3:33"
    assert _format_duration(3930.9) == "1:05:30"
```

---

## 5. Archivos a modificar

### 5.1 `src/yt_links_mp3/cli.py`

**Líneas 144-150** (función `_format_duration`):

```diff
 def _format_duration(seconds: int | float | None) -> str:
-    """Formatea segundos a MM:SS."""
+    """Formatea segundos a M:SS o H:MM:SS según corresponda.
+
+    Ejemplos:
+        213 (3:33)         → '3:33'
+        3599 (59:59)       → '59:59'
+        3600 (1:00:00)     → '1:00:00'
+        3930 (1h 5m 30s)   → '1:05:30'
+        None o 0           → '?'
+    """
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

### 5.2 `tests/test_cli.py`

Agregar los tests descritos en §4.3.

---

## 6. Comandos de verificación

```bash
# 1. Verificar la función en REPL
python -c "from yt_links_mp3.cli import _format_duration; print(_format_duration(3930))"
# Debe imprimir: 1:05:30

# 2. Correr tests nuevos
pytest tests/test_cli.py::test_format_duration -v
pytest tests/test_cli.py::test_format_duration_accepts_float_seconds -v

# 3. Correr toda la suite
pytest

# 4. Smoke test con un video largo (opcional)
yt-links-mp3 info "https://www.youtube.com/watch?v=4xDzrJKXOOY"
# (Boiler Room live set, ~1h)
# Debe mostrar duración tipo '1:00:23' en vez de '60:23'
```

---

## 7. Edge cases y consideraciones

### 7.1 ¿Por qué no `H:MM:SS` siempre (uniforme)?

Decisión de UX: para videos cortos (3:33), el formato `0:03:33` es ruido visual. El umbral de 1h es natural y consistente con la mayoría de los reproductores de video (VLC, mpv, etc.).

### 7.2 ¿Por qué no zero-pad las horas?

Decisión de UX: 1h, 2h, 10h — todos se ven bien sin padding (`1:05:30`, `10:00:00`). Si quisiéramos uniformidad con minutos/segundos, sería `01:05:30`, pero ese caso es raro (live sets de >10h son infrecuentes).

### 7.3 ¿Qué pasa con duraciones negativas o NaN?

No deberían llegar a esta función (yt-dlp retorna siempre `int` o `None`). Pero por defensa:

```python
>>> _format_duration(-1)   # retorna '?' (truthiness falla)
>>> _format_duration(float('nan'))  # retorna '?' (truthiness falla)
```

`if not seconds` cubre ambos casos (`bool(-1)` es True, pero `bool(0)` es False → no es perfecto, pero acceptable).

Si quisiéramos ser rigurosos:

```python
if not seconds or seconds < 0:
    return "?"
```

Pero esto es fuera de scope.

### 7.4 ¿Afecta a la tabla de `info <archivo>`?

La tabla usa `_format_duration(info_dict.get("duration"))` (cli.py:258). El fix aplica automáticamente. Los anchos de columna pueden necesitar ajuste si se introduce `H:MM:SS` (8 chars vs 5 chars de `M:SS`), pero la tabla es generada por `rich` que ajusta el ancho automáticamente.

### 7.5 ¿Formato regional (europeo vs americano)?

Siempre `:` como separador (convención internacional). No se implementa i18n.

---

## 8. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Cambio en output rompe expectations de usuarios que parsean la salida | Muy baja | Bajo | El output nunca fue formalmente estable; el README no documenta el formato exacto |
| Tests parametrizados flaky por floats | Muy baja | Bajo | Solo se testea con `int` o `float` truncado (ver `test_format_duration_accepts_float_seconds`) |
| Tabla de `rich` se ve mal con anchos mixtos (algunos 5 chars, otros 8) | Baja | Cosmético | `rich.Table` ajusta el ancho automáticamente; verificar manualmente |

---

## 9. Checklist de cierre (para el implementador)

- [ ] Modificada la función `_format_duration` en `cli.py:144-150`
- [ ] Actualizado el docstring con ejemplos
- [ ] Agregados los tests parametrizados en `tests/test_cli.py`
- [ ] Correr `pytest` → 137/137 pasando (125 + 12 casos del parametrize)
- [ ] Smoke test manual con un video de >1h (ej: Boiler Room)
- [ ] Commit con mensaje: `fix(cli): format durations >= 1h as H:MM:SS instead of MM:SS`
- [ ] Push

---

## 10. Open questions

1. **¿Vale la pena mover `_format_duration` a `utils.py` o `metadata.py`?** → **Decisión**: fuera de scope. Si en el futuro se reusa en otro lado, mover.
2. **¿Deberíamos usar `datetime.timedelta` para más robustez?** → **Decisión**: no, agregaría dependencia de stdlib innecesaria. La función actual es 6 líneas y trivial de leer.
3. **¿Vale la pena mostrar la duración en formato ISO 8601 (`PT1H5M30S`)?** → **Decisión**: no, ese formato es verbose y pensado para máquinas, no para humanos en consola.

---

## 11. Referencias

- Función actual: `cli.py:144-150`.
- Caso de uso afectado: `PLAN.md:109` (Boiler Room live set).
- Tests existentes: `tests/test_cli.py` (estructura a seguir para los nuevos).
- Reporte de análisis post-Phase 5 (issue 🟡 Media #3).