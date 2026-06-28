# PLAN.md — yt-links-mp3

Plan de implementación por fases, pensado para entregar valor temprano y validar las decisiones de diseño antes de escalar.

---

## 🎯 Objetivo

Construir una herramienta CLI que lea un archivo de texto con URLs de videos individuales de YouTube (uno por línea) y descargue cada uno como MP3 con metadatos limpios, portada embebida y una estructura de carpetas ordenada por artista/álbum.

---

## 🧭 Decisiones de diseño (ADR-lite)

| # | Decisión | Razón | Alternativas descartadas |
|---|----------|-------|--------------------------|
| 1 | Usar `yt-dlp` sobre `youtube-dl` | Mantenido activamente, mejor soporte de URLs individuales, postprocesado más estable | `youtube-dl` (abandonado), `pytube` (frágil) |
| 2 | CLI en Python + `click` | Ecosistema maduro, fácil de empaquetar, tests sencillos | Node.js (overkill), Go (recompilar deps), Bash (mantenimiento) |
| 3 | Concurrencia con `ThreadPoolExecutor` | yt-dlp es I/O bound, threads son suficientes y simples | `asyncio` (overkill para subprocess), `multiprocessing` (más memoria) |
| 4 | Postprocesado con `ffmpeg` directo | Control total sobre bitrate/metadatos, sin intermediarios | `mutagen` (solo metadatos, no convierte), `pydub` (envuelve ffmpeg) |
| 5 | Config en YAML + pydantic | Validación, autocompletado, separación código/config | TOML (menos legible), JSON (sin comentarios) |
| 6 | Nombres por metadatos (no por título de video) | Un mismo video puede tener título "raro" pero artista/título correctos | Usar `--output` de yt-dlp directo (limitado) |
| 7 | **Parser del archivo de links tolerante** | Aceptar líneas vacías, comentarios `#`, espacios, URLs con/sin `https://`, IDs solos (`dQw4w9WgXcQ`) | Parser estricto (frágil ante edición manual) |
| 8 | Empaquetar como CLI instalable (`pip install -e .`) | Una vez instalado, se invoca como comando nativo | Script suelto (depende de PYTHONPATH) |

---

## 🏗️ Arquitectura

```
yt-links-mp3/
├── pyproject.toml
├── README.md
├── PLAN.md
├── config.example.yaml
├── links.example.txt          # archivo de ejemplo con URLs
├── src/
│   └── yt_links_mp3/
│       ├── __init__.py
│       ├── cli.py              # entrypoint click (comandos: download, info, validate)
│       ├── config.py           # pydantic-settings
│       ├── linklist.py         # parser del archivo de URLs
│       ├── downloader.py       # orquesta descargas (ThreadPoolExecutor)
│       ├── paths.py            # plantillas de paths seguros (sanitización)
│       ├── progress.py         # barras rich
│       └── logging.py          # loguru config
└── tests/
    └── test_linklist.py        # parser de links
```

> Los módulos `metadata.py` y `postprocess.py` se agregarán en Fase 2.

### Flujo de datos

```
links.txt
   │
   ▼
parse_link_file()          → list[LinkEntry(url, line_number, raw)]
   │
   ▼ (filter vacíos, comentarios, dedupe preservando orden)
list[LinkEntry]
   │
   ▼
ThreadPoolExecutor
   │  ┌───────────────────────┐
   │  ▼                       ▼                       ▼
download_audio        download_audio          download_audio
(yt-dlp bestaudio)    (yt-dlp bestaudio)      (yt-dlp bestaudio)
   │                       │                       │
   └───────────────────────┼───────────────────────┘
                           ▼
                  postprocess_to_mp3
                  (ffmpeg + metadatos + cover)
                           │
                           ▼
                  output_dir/<Artist>/<Album>/NN - Title.mp3
```

---

## 📄 Formato del archivo de links (`links.txt`)

```text
# Comentarios con # son ignorados
# Líneas vacías también se ignoran
# Las URLs pueden estar solas o tener descripción opcional después de un espacio

# --- Canciones sueltas ---
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/jNQXAC9IVRw          Rick Astley clásico
dQw4w9WgXcQ                            # También acepta solo el ID

# --- Mezclando canales ---
https://www.youtube.com/watch?v=9bZkp7q19f0   Gangnam Style
https://www.youtube.com/watch?v=kJQP7kiw5Fk   Despacito

# --- Live sets largos ---
https://www.youtube.com/watch?v=4xDzrJKXOOY   Boiler Room (mezcla 1h)
```

### Reglas del parser

| Caso | Comportamiento |
|---|---|
| Línea vacía | Ignorada |
| Línea que empieza con `#` | Ignorada (comentario) |
| Línea que empieza con `//` | Ignorada (comentario estilo code) |
| URL completa `https://...` | Aceptada |
| URL corta `youtu.be/<id>` | Aceptada, normalizada |
| Solo el ID de video (11 chars alfanuméricos + `-_`) | Aceptada, expandida a `https://youtu.be/<id>` |
| Texto después de la URL (separado por espacios o tab) | Se guarda como `description` opcional (puede usarse como hint para metadatos) |
| URL duplicada | Se deduplica preservando la primera aparición |
| Línea que no matchea nada | Warning + skip (no aborta) |
| Encoding | UTF-8 estricto, BOM tolerado |

---

## 📅 Fases

### Fase 0 — Bootstrap (1h)
- [x] Crear repo con `README.md` y `PLAN.md`
- [x] `git init`, branch `main`, `.gitignore` para Python
- [x] Renombrar proyecto a `yt-links-mp3` (paquete y CLI)
- [x] `pyproject.toml` con deps: `yt-dlp`, `click`, `pydantic`, `pyyaml`, `loguru`, `rich`
- [x] Estructura de carpetas `src/` y `tests/`
- [x] `config.example.yaml` y `links.example.txt`
- [x] Repo remoto en GitHub
- [x] Virtualenv creado (Python 3.11 disponible vía Homebrew)
- [x] Paquete instalable: `pip install -e .` deja `yt-links-mp3` disponible en PATH

### Fase 1 — MVP funcional (4–6h)
- [x] `linklist.py`: parser del archivo de links (comentarios, vacíos, IDs solos, dedupe)
- [x] `cli.py` con comando `download <archivo.txt>` que toma el archivo como argumento
- [x] `cli.py` con comando `validate <archivo.txt>` que muestra cuántos links válidos hay sin descargar
- [x] `downloader.py`: por cada URL, usa `yt-dlp` para descargar `bestaudio` y convertir a MP3 con `ffmpeg` postprocess
- [x] `paths.py`: sanitiza nombres de archivo (caracteres prohibidos, longitud máxima)
- [x] `progress.py`: barra de progreso global con `rich`
- [x] Logging a consola con `loguru`
- [ ] Salida por defecto: `~/Music/Downloads/<Artist>/<Album>/NN - Title.mp3` *(queda Fase 2: hoy sale plano como `~/Music/Downloads/<id>.mp3`)*

**Criterio de aceptación:** dado un `links.txt` con 10 URLs de videos individuales, produce 10 MP3s válidos en menos de 5 minutos.

#### Decisiones de implementación de Fase 1
- **Descargas en serie por ahora** (en `cli.py`). `downloader.download_all()` ya existe con `ThreadPoolExecutor`, pero `cli.download` itera secuencial para mantener la barra de progreso exacta. Migración a paralelo con callback de progress queda para Fase 3.
- **Outputs flat por ahora**: yt-dlp escribe `<id>.mp3` en `output_dir` (no estructura por artista/álbum aún).
- **Sanitización ya implementada** (`paths.sanitize_component`) pero no aplicada a outputs en Fase 1 (Fase 2).
- **9/9 tests pasando** en `tests/test_linklist.py`.

### Fase 2 — Metadatos ricos (3–4h)
- [ ] `metadata.py`: extraer artista/título/álbum de la descripción/título del video con heurísticas
- [ ] Soporte para `description` del archivo de links como hint de metadatos
- [ ] `postprocess.py`: embeber metadatos (ID3v2.4) y portada con `ffmpeg`
- [ ] Nombres por plantilla: `{artist}/{album}/{track_number:02d} - {title}.{ext}`
- [ ] Descargar `cover.jpg` de maxresdefault si está disponible
- [ ] Opción `--folder-template` para organizar (default: por artista, alternativo: flat, por fecha, etc.)

**Criterio de aceptación:** los MP3s se ven correctamente en iTunes/VLC/Files.app con carátula y metadatos.

### Fase 3 — Robustez (2–3h)
- [ ] `config.yaml` con todas las opciones (output_dir, concurrency, quality, dry-run, etc.)
- [ ] Flag `--dry-run` que muestra qué se descargaría sin escribir
- [ ] Flag `--force` para re-descargar
- [ ] Flag `--continue` que reanuda desde donde falló (lee `links.txt.failed` generado)
- [ ] Skip automático de videos ya descargados (hash por ID + duración)
- [ ] Manejo de errores: reintentos (3x con backoff), continuar si un video falla
- [ ] Resumen final: N exitosos, M fallidos, con lista de fallos → escribe `links.txt.failed`
- [ ] Al terminar, si hubo fallos, sugiere: `yt-links-mp3 download links.txt.failed`

**Criterio de aceptación:** un archivo con 50 links, 2 privados y 1 roto, termina con 48 archivos y `links.txt.failed` con los 3 que fallaron.

### Fase 4 — Calidad y DX (2–3h)
- [ ] Tests unitarios para `linklist.py`, `paths.py`, `metadata.py`, `config.py`
- [ ] `pre-commit` con `ruff` + `black`
- [ ] CI con GitHub Actions (lint + tests en matrix Python 3.11/3.12)
- [ ] `Makefile` con targets: `install`, `test`, `lint`, `run`
- [ ] Comando `info <link>` que muestra metadata de un video sin descargar
- [ ] Comando `info <archivo.txt>` que muestra tabla resumen (título, artista detectado, duración, ya descargado sí/no)

### Fase 5 — Pulido (opcional)
- [ ] Watch mode: si modificás `links.txt`, descarga los nuevos
- [ ] Cache de metadatos para evitar refetch
- [ ] Integración con `beets` o `MusicBrainz` para arreglar metadatos
- [ ] Auto-organizar en estructura `{artist}/{year - album}/` si hay año disponible
- [ ] Soporte para SoundCloud, Bandcamp (vía yt-dlp)
- [ ] Empaquetado para `brew tap` o `pipx`

---

## 🧪 Cómo testear manualmente

```bash
# 1. Crear un archivo de prueba
cat > /tmp/links.txt <<EOF
# Canciones de prueba
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/watch?v=9bZkp7q19f0
dQw4w9WgXcQ  # ID solo (debe ser dedupe'd)
EOF

# 2. Validar (sin descargar)
yt-links-mp3 validate /tmp/links.txt

# 3. Dry-run
yt-links-mp3 download /tmp/links.txt --dry-run

# 4. Descargar de verdad
yt-links-mp3 download /tmp/links.txt -o /tmp/test

# 5. Verificar
ls -la /tmp/test/
ffprobe "/tmp/test/<archivo>.mp3"
```

Verificar:
- El ID duplicado (`dQw4w9WgXcQ`) aparece solo una vez
- Comentarios y líneas vacías no generan downloads
- Archivos con nombres consistentes
- `ffprobe archivo.mp3` muestra metadatos
- Portada visible en Finder/VLC
- No quedan archivos `.part` o `.tmp`

---

## 🔧 Ejemplo de uso real (workflow típico)

```bash
# Día 1: armás tu archivo de links curado
vim ~/Music/links.txt
# Pegás URLs a mano, con descripciones opcionales

# Día 1: descargás todo
yt-links-mp3 download ~/Music/links.txt

# Días siguientes: agregás más links y volvés a correr
vim ~/Music/links.txt
yt-links-mp3 download ~/Music/links.txt
# → skip automático de los que ya están descargados

# Si algo falló (video privado, geo-block, etc.):
cat ~/Music/links.txt.failed     # solo los que fallaron
yt-links-mp3 download ~/Music/links.txt.failed  # reintenta esos
```

---

## ⚠️ Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| YouTube cambia la firma de las URLs y `yt-dlp` se rompe | Pin a versión estable de `yt-dlp`; documentar cómo actualizar |
| `ffmpeg` no instalado en el sistema | Verificar en `cli.py` y abortar con mensaje claro |
| Archivo de links mal formateado (URLs inválidas, encoding raro) | Parser tolerante: warn + skip líneas malas, no abortar |
| Metadatos sucios (track con "Official Video" en el título) | Heurísticas de limpieza en `metadata.py`; permitir override manual |
| Copyright / DMCA | Disclaimer prominente en README; el proyecto es personal |
| Rate limiting de YouTube | Concurrencia baja por defecto (3), respeto a `--limit-rate` de yt-dlp |
| El usuario pone la misma URL dos veces sin darse cuenta | Dedupe preservando orden + warning "URL duplicada en línea N" |

---

## 📊 Estimación restante

~6–10 horas para llegar a Fase 3 funcional (metadatos + robustez). Fase 4 y 5 son nice-to-have.

---

## 🚦 Estado actual

**Fase:** 1 — MVP funcional ✅ (descarga básica operativa, falta estructura de carpetas y naming por metadatos)
**Próximo paso:** Fase 2 — Metadatos ricos + estructura de carpetas por artista/álbum

### Lo que funciona hoy
- `yt-links-mp3 validate <archivo.txt>` → cuenta links válidos y reporta líneas ignoradas
- `yt-links-mp3 download <archivo.txt>` → descarga secuencial con barra de progreso, log de fallos, y genera `links.txt.failed` para reintentar
- `yt-links-mp3 download --dry-run` → preview sin tocar disco
- `yt-links-mp3 download --concurrency N` → *override disponible pero no aplicado (loop secuencial en cli)*
- Outputs en `~/Music/Downloads/<video_id>.mp3` (flat, sin estructura de artista/álbum — viene en Fase 2)
- Calidad por defecto: 320 kbps (CBR, máximo para MP3)
- Tests: 9/9 pasando

### Notas operativas
- **Python 3.11 disponible** vía Homebrew (`/opt/homebrew/bin/python3.11`). `pyproject.toml` declara `>=3.9`.
- **ffmpeg** requerido por yt-dlp para el postprocess a MP3.

---
