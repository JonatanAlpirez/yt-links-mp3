# SPEC-001: Fix de YAML inválido en `config.example.yaml`

| Campo | Valor |
|---|---|
| **ID** | SPEC-001 |
| **Título** | `config.example.yaml` falla al cargar por uso incorrecto de comillas en strings con regex |
| **Severidad** | 🔴 Crítica |
| **Estado** | Draft → Ready for implementation |
| **Archivos afectados** | `config.example.yaml`, `README.md`, `tests/test_config.py` (nuevo) |
| **Esfuerzo estimado** | 30–45 min |
| **Riesgo de regresión** | Bajo (cambios solo en documentación + 1 archivo de tests nuevo) |

---

## 1. Contexto

El archivo `config.example.yaml` que el proyecto distribuye como plantilla de configuración **no puede ser cargado por `yaml.safe_load`**. Cualquier usuario que lo copie a `~/.config/yt-links-mp3/config.yaml` obtendrá un error de parseo al ejecutar la CLI.

### 1.1 Reproducción

```bash
$ python -c "import yaml; yaml.safe_load(open('config.example.yaml').read())"
yaml.scanner.ScannerError: while scanning a double-quoted scalar
  in "<unicode string>", line 27, column 5:
      - "\(official video\)"
        ^
found unknown escape character '('
```

### 1.2 Causa raíz

Las regex de limpieza usan caracteres de escape (`\(`, `\)`, `\b`) que en YAML, dentro de **double-quoted strings**, se interpretan como **escape sequences estilo JSON**:

| En YAML | Se interpreta como |
|---|---|
| `"\(official\)"` | `ScannerError` — `\(` no es escape válido |
| `"\bhd\b"` | String con bytes `0x08 0x68 0x64 0x08` (backspace + "hd" + backspace), NO es word boundary regex |

El bloque afectado está en `config.example.yaml` líneas 27–42 (la lista `cleanup_patterns`).

### 1.3 Impacto

- **Funcional**: `cleanup_patterns` no puede customizarse desde YAML. El usuario queda forzado a usar los defaults hardcodeados en `metadata.DEFAULT_CLEANUP_PATTERNS`.
- **UX**: El error es críptico (apunta a la línea del patrón) y no menciona que es un problema de quoting.
- **Documentación**: El bloque YAML del `README.md` (sección "Configuración") tiene el mismo bug → seguir las instrucciones del README rompe la config.

---

## 2. Scope

### 2.1 Dentro de scope

- Corregir el quoting de strings regex en `config.example.yaml`.
- Corregir el quoting en el bloque YAML mostrado en `README.md`.
- Agregar un test de regresión que verifique que `config.example.yaml` carga correctamente con `Config.load()`.
- Documentar la convención de quoting en un comentario dentro del YAML ejemplo.

### 2.2 Fuera de scope

- Cambiar el formato del config (sigue siendo YAML).
- Cambiar el parser ni agregar lógica custom de escape handling.
- Migrar a otro formato (TOML, JSON).
- Refactorizar `Config` o el sistema de cleanup patterns.
- Cualquier cambio a `metadata.py` o `paths.py`.

---

## 3. Solución propuesta

### 3.1 Decisión de diseño

**Elegido: usar single-quoted strings para todas las regex.**

Justificación:

| Estilo | Carga en YAML | Mantenible | Legible |
|---|---|---|---|
| Double-quoted `"\(official\)"` | ❌ Rompe | Bajo (necesita escaping) | Bajo |
| **Single-quoted `'\(official\)'`** | ✅ OK | Alto | Alto |
| Plain (sin comillas) `\bofficial\b` | ⚠️ Frágil (espacios/comentarios rompen) | Medio | Alto |

YAML single-quoted strings **no procesan backslash escapes** — el contenido es literal. Esto preserva las regex tal cual las escribiría el desarrollador en Python.

### 3.2 Patrón de reemplazo

Aplicar la siguiente transformación a cada línea de la lista `cleanup_patterns`:

```diff
-  - "\(official video\)"
+  - '\(official video\)'
```

---

## 4. Criterios de aceptación

El spec se considera completo cuando **TODAS** estas condiciones son verdaderas:

### 4.1 Funcionales

- [ ] `yaml.safe_load(Path('config.example.yaml').read_text())` retorna un dict sin errores.
- [ ] `Config.load('config.example.yaml')` retorna una instancia de `Config` válida.
- [ ] `Config.load('config.example.yaml').cleanup_patterns` es una lista de 16 strings donde cada string es exactamente la regex literal esperada (ver §4.3).
- [ ] `cleanup_title("Song (Official Video)", patterns=Config.load('config.example.yaml').cleanup_patterns)` retorna `"Song"`.

### 4.2 No regresión

- [ ] Los 63 tests existentes siguen pasando.
- [ ] Los 4 tests nuevos agregados (§4.4) pasan.
- [ ] No se modificó ningún archivo en `src/yt_links_mp3/` excepto lo descrito en §5.

### 4.3 Valores esperados de `cleanup_patterns` después del fix

La lista debe contener, en este orden exacto, estos strings (verificables con assert en el test):

```python
EXPECTED_PATTERNS = [
    r"\(official video\)",
    r"\(official music video\)",
    r"\[official video\]",
    r"\(official\)",
    r"\[official\]",
    r"\(lyric(?:s)? video\)",
    r"\(lyric(?:s)?\)",
    r"\(lyrics?\)",
    r"\(hd\)",
    r"\[hd\]",
    r"\bhd\b",
    "official video",
    "official music video",
    "music video",
    r"\blyric(?:s)? video\b",
    r"\blyrics?\b",
]
```

### 4.4 Tests a agregar

**Archivo nuevo: `tests/test_config.py`**

```python
"""Tests para config.py — carga y defaults."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from yt_links_mp3.config import Config


def test_example_config_loads_without_error() -> None:
    """El config.example.yaml del repo debe cargar sin errores."""
    example_path = Path(__file__).parent.parent / "config.example.yaml"
    assert example_path.exists(), "config.example.yaml debe existir en la raíz"
    config = Config.load(example_path)
    assert isinstance(config, Config)


def test_example_config_cleanup_patterns_are_valid_regex() -> None:
    """Los cleanup_patterns deben ser regex compilables."""
    example_path = Path(__file__).parent.parent / "config.example.yaml"
    config = Config.load(example_path)
    for pattern in config.cleanup_patterns:
        # No debe lanzar re.error
        re.compile(pattern)


def test_example_config_cleanup_patterns_match_expected() -> None:
    """Los cleanup_patterns deben contener exactamente las regex esperadas."""
    example_path = Path(__file__).parent.parent / "config.example.yaml"
    config = Config.load(example_path)
    expected = [
        r"\(official video\)",
        r"\(official music video\)",
        r"\[official video\]",
        r"\(official\)",
        r"\[official\]",
        r"\(lyric(?:s)? video\)",
        r"\(lyric(?:s)?\)",
        r"\(lyrics?\)",
        r"\(hd\)",
        r"\[hd\]",
        r"\bhd\b",
        "official video",
        "official music video",
        "music video",
        r"\blyric(?:s)? video\b",
        r"\blyrics?\b",
    ]
    assert config.cleanup_patterns == expected


def test_example_config_cleanup_patterns_actually_clean_title() -> None:
    """Smoke test: aplicar los patterns debe limpiar un título real."""
    from yt_links_mp3.metadata import cleanup_title

    example_path = Path(__file__).parent.parent / "config.example.yaml"
    config = Config.load(example_path)
    result = cleanup_title(
        "Never Gonna Give You Up (Official Video)",
        patterns=config.cleanup_patterns,
    )
    assert result == "Never Gonna Give You Up"


def test_readme_yaml_block_is_valid() -> None:
    """El bloque YAML de ejemplo en README.md debe ser parseable."""
    readme = Path(__file__).parent.parent / "README.md"
    content = readme.read_text(encoding="utf-8")

    # Buscar el bloque YAML dentro de triple-backticks con tag yaml
    matches = re.findall(r"```yaml\n(.*?)\n```", content, re.DOTALL)
    assert matches, "README debe contener al menos un bloque YAML"

    for i, block in enumerate(matches):
        try:
            yaml.safe_load(block)
        except yaml.YAMLError as e:
            pytest.fail(f"Bloque YAML #{i} del README no es válido: {e}")
```

---

## 5. Archivos a modificar

### 5.1 `config.example.yaml`

**Líneas 27–42** (la lista `cleanup_patterns`):

Cambiar todas las comillas dobles por comillas simples. Diff completo:

```diff
 # Regex (case-insensitive) a borrar del título al limpiar.
 # Extensible: agregar/quitar entradas según necesidad.
+# IMPORTANTE: usar single quotes para que YAML no interprete \ como escape.
 cleanup_patterns:
-  - "\(official video\)"
-  - "\(official music video\)"
-  - "\[official video\]"
-  - "\(official\)"
-  - "\[official\]"
-  - "\(lyric(?:s)? video\)"
-  - "\(lyric(?:s)?\)"
-  - "\(lyrics?\)"
-  - "\(hd\)"
-  - "\[hd\]"
-  - "\bhd\b"
-  - "official video"
-  - "official music video"
-  - "music video"
-  - "\blyric(?:s)? video\b"
-  - "\blyrics?\b"
+  - '\(official video\)'
+  - '\(official music video\)'
+  - '\[official video\]'
+  - '\(official\)'
+  - '\[official\]'
+  - '\(lyric(?:s)? video\)'
+  - '\(lyric(?:s)?\)'
+  - '\(lyrics?\)'
+  - '\(hd\)'
+  - '\[hd\]'
+  - '\bhd\b'
+  - 'official video'
+  - 'official music video'
+  - 'music video'
+  - '\blyric(?:s)? video\b'
+  - '\blyrics?\b'
```

### 5.2 `README.md`

**Sección "Configuración (`config.yaml`)"** (alrededor de líneas 195–207):

Aplicar la misma transformación `"\(..."` → `'\(...'` al bloque YAML embebido. Verificar que no haya otros bloques YAML en el README con el mismo problema.

### 5.3 `tests/test_config.py` (archivo nuevo)

Crear con el contenido del §4.4.

---

## 6. Comandos de verificación

Después de aplicar los cambios, ejecutar:

```bash
# 1. Verificar que el YAML carga
python -c "import yaml; print(yaml.safe_load(open('config.example.yaml').read()))"

# 2. Verificar que Config.load funciona
python -c "from yt_links_mp3.config import Config; print(Config.load('config.example.yaml').cleanup_patterns[0])"
# Debe imprimir: \(official video\)

# 3. Correr toda la suite de tests
pytest

# 4. Verificar específicamente el nuevo test
pytest tests/test_config.py -v

# 5. Verificar que el README no tiene bloques YAML rotos
python -c "
import re, yaml
from pathlib import Path
readme = Path('README.md').read_text()
blocks = re.findall(r'\`\`\`yaml\n(.*?)\n\`\`\`', readme, re.DOTALL)
for i, b in enumerate(blocks):
    try:
        yaml.safe_load(b)
        print(f'Block {i}: OK')
    except yaml.YAMLError as e:
        print(f'Block {i}: FAIL - {e}')
"
```

Todos los comandos del paso 1–5 deben terminar sin errores.

---

## 7. Edge cases y consideraciones

### 7.1 ¿Por qué no plain scalars (sin comillas)?

Plain scalars en YAML funcionan para `\bofficial\b` siempre que el string no contenga:
- `#` (sería interpretado como comentario)
- `:` seguido de espacio (sería interpretado como mapping)
- Leading/trailing whitespace
- Strings que parecen booleanos (`yes`, `no`, `true`, `false`) — se interpretan como tales

Una regex como `r"(official|video)"` con `|` se parsearía como bloque literal en algunos YAML loaders. Single quotes evitan toda esta fragilidad.

### 7.2 ¿Por qué no agregar escape handling custom a Config?

Tres razones:

1. Esconde el problema. Mejor que el usuario vea el YAML correcto.
2. Rompe el principio de least surprise: dos formatos diferentes (default en código vs YAML custom) podrían divergir.
3. Los defaults (`DEFAULT_CLEANUP_PATTERNS` en `metadata.py`) ya están como raw strings de Python. El YAML debe matchear.

### 7.3 Compatibilidad con Python < 3.12

El spec no introduce código Python nuevo. Los tests usan `pytest` estándar y `re`/`yaml`/`pathlib`. Compatible con `>=3.9` declarado en `pyproject.toml`.

### 7.4 ¿Afecta el `Config.load()` cuando NO hay config?

No. `Config.load(None)` y `Config.load("/path/inexistente")` retornan `Config()` con defaults. El bug solo afecta cuando el usuario pasa explícitamente el `config.example.yaml` (o cualquier config que use double-quoted regex).

---

## 8. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Cambiar comillas rompa el matching de patterns en otro lado | Baja | Bajo | Test §4.3 verifica que los patterns son idénticos byte-a-byte |
| Se pierdan patterns al hacer find-replace | Baja | Medio | Diff exacto provisto en §5.1 — usar copy-paste, no sed |
| Otros bloques YAML en README/PLAN tengan el mismo bug | Media | Bajo | Test §4.4 los cubre; ejecutar paso 5 de §6 manualmente |
| El usuario ya tiene un `config.yaml` con el formato viejo | Baja | Bajo | El error es visible al primer `yt-links-mp3` invocation; no hay migración silenciosa |

---

## 9. Checklist de cierre (para el implementador)

- [ ] Modificado `config.example.yaml` líneas 27–42 (16 strings) + comentario sobre quoting
- [ ] Modificado `README.md` bloque YAML de sección Configuración
- [ ] Creado `tests/test_config.py` con 5 tests
- [ ] Correr `pytest` → 68/68 passing (63 existentes + 5 nuevos)
- [ ] Correr comandos de §6 → todos OK
- [ ] `git diff` revisado para confirmar solo cambios esperados
- [ ] Commit con mensaje: `fix: use single quotes in cleanup_patterns YAML to avoid escape conflict`

---

## 10. Open questions

1. **¿Vale la pena agregar un test que lea `PLAN.md` también?** PLAN no contiene bloques YAML hoy, pero podría en el futuro. → **Decisión**: fuera de scope. Si se agrega, en un spec separado.
2. **¿Deberíamos hacer un linter de YAML en CI?** → **Decisión**: fuera de scope. Es un enhancement nice-to-have para Fase 4.
3. **¿Vale la pena agregar un warning si `Config.load()` recibe un YAML que parece tener escapes rotos?** → **Decisión**: no, falsos positivos serían molestos. Mejor corregir el archivo.

---

## 11. Referencias

- Bug detectado en análisis post-Phase 2 (issue **N1**/**N2** del informe).
- YAML spec sobre escape sequences: https://yaml.org/spec/1.2.2/#57-escaped-characters
- Discusión previa del proyecto: `PLAN.md` sección "Riesgos y mitigaciones".