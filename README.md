# 🎵 yt-links-mp3

Descargador de música a partir de un **archivo de texto con URLs** (una por línea). Convierte cada video a MP3 con `yt-dlp` + `ffmpeg`. Soporta YouTube y otros sitios compatibles con `yt-dlp` (SoundCloud, Bandcamp, Vimeo, etc.).

> Pensado para uso personal: vos armás una lista curada de links en un `.txt`, y la herramienta los descarga uno a uno. Sin login, sin scraping de playlist, sin sorpresas.

---

## ✨ Características

- Lee un archivo de texto con URLs de videos (uno por línea) — soporta YouTube y sitios compatibles con `yt-dlp` (SoundCloud, Bandcamp, Vimeo, etc.).
- Parser tolerante: comentarios (`#`, `//`), líneas vacías, IDs solos (`dQw4w9WgXcQ`), dedupe automático.
- Convierte cada video a MP3 con `yt-dlp` + `ffmpeg` a 320 kbps (CBR) por defecto.
- Metadata limpia automáticamente: regex borra `Official Video`, `HD`, `(Lyric)`, etc.
- Portada embebida en cada MP3 (ID3v2.4 cover art) — sin archivos sueltos.
- Modo dry-run para previsualizar sin escribir a disco.
- Auto-reanudación: si un link falla, se escribe a `links.txt.failed` para reintentar.
- Reintentos automáticos con backoff exponencial (1s, 5s, 15s por defecto) en errores de red. Errores permanentes (video privado, eliminado, 404, age-restricted) no se reintentan.
- Concurrencia configurable (default: 3 workers en paralelo).
- Cache persistente de metadata: evita llamadas repetidas a `yt-dlp` cuando el mismo video aparece en varios archivos.
- Comando `info` para ver metadata de un link o archivo sin descargar.
- Configuración por archivo YAML.
- Empaquetable con `pipx` para uso como comando global.

Roadmap y features pendientes: ver [`PLAN.md`](./PLAN.md).

---

## 🧰 Stack

| Componente            | Tecnología                                | Por qué                                                                 |
| --------------------- | ----------------------------------------- | ----------------------------------------------------------------------- |
| Descarga de video     | [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) | Mantenido, soporte de URLs individuales, selectores de formato, postprocesado. |
| Extracción de audio   | `ffmpeg`                                  | Estándar de facto para muxing/conversión.                               |
| Lenguaje              | Python 3.10+ (probado en 3.11 y 3.12 en CI) | Ecosistema, scripts, CLI limpio. |
| CLI                   | [`click`](https://palletsprojects.com/p/click/) | Argumentos tipados, subcomandos, experiencia pro.                     |
| Config                | `pydantic` + YAML                        | Validación + archivo de config legible.                                |
| Logging               | `loguru`                                  | Salida colorida en consola + archivo rotado.                            |
| Progreso              | `rich`                                    | Barras de progreso y tablas bonitas.                                    |
| Tests                 | `pytest`                                  | Estándar del ecosistema.                                                |
| Empaquetado           | `uv` o `pip` + `pyproject.toml`           | Dependencias declarativas, instalable como CLI.                         |

---

## 📦 Instalación

El proyecto es Python puro y multiplataforma (macOS, Linux, Windows). Lo único externo que necesitás es `ffmpeg` para la conversión a MP3.

### 1. Dependencias de sistema

| SO | Cómo instalar ffmpeg |
| --- | --- |
| **macOS** | `brew install ffmpeg` |
| **Debian / Ubuntu** | `sudo apt update && sudo apt install ffmpeg` |
| **Fedora** | `sudo dnf install ffmpeg` |
| **Arch / Manjaro** | `sudo pacman -S ffmpeg` |
| **Windows** | `winget install ffmpeg` (recomendado) <br> o descargar el build desde [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) y agregar la carpeta `bin` al `PATH` |

> ✅ Verificá que esté disponible: `ffmpeg -version` debe responder.

### 2. Clonar e instalar el proyecto

#### macOS / Linux

```bash
git clone https://github.com/JonatanAlpirez/yt-links-mp3.git
cd yt-links-mp3
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Opcional: instalar pytest para correr los tests
pip install pytest
```

#### Windows (PowerShell)

```powershell
git clone https://github.com/JonatanAlpirez/yt-links-mp3.git
cd yt-links-mp3
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .

# Opcional: instalar pytest para correr los tests
pip install pytest
```

#### Windows (CMD)

```cmd
git clone https://github.com/JonatanAlpirez/yt-links-mp3.git
cd yt-links-mp3
python -m venv .venv
.venv\Scripts\activate.bat
pip install -e .
```

> 💡 Si PowerShell bloquea la activación del venv con un error de "running scripts is disabled", ejecutá una sola vez:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

> El comando `yt-links-mp3` quedará disponible en tu shell mientras el venv esté activado. En Windows también funciona desde PowerShell y CMD.

#### Instalación global con `pipx` (recomendado para uso personal)

Si solo querés usar el CLI sin desarrollar, `pipx` lo instala en un venv aislado y expone el comando globalmente:

```bash
# macOS / Linux
brew install pipx          # o: python3 -m pip install --user pipx
pipx ensurepath

# Instalar desde el repo local
pipx install .

# O desde GitHub directo (sin clonar)
pipx install git+https://github.com/JonatanAlpirez/yt-links-mp3.git
```

Después podés invocar `yt-links-mp3` desde cualquier directorio:

```bash
yt-links-mp3 download ~/Music/links.txt
yt-links-mp3 info dQw4w9WgXcQ
```

> Requisito: Python 3.10+ en el sistema (lo declara el `pyproject.toml`).

### 3. Requisitos de Python

Probado en Python 3.11 y 3.12. `pyproject.toml` declara `>=3.10`.

| SO | Instalar Python 3.11+ |
| --- | --- |
| **macOS** | `brew install python@3.11` y luego `python3.11 -m venv .venv` |
| **Windows** | Descargar desde [python.org](https://www.python.org/downloads/) (marcá "Add Python to PATH" en el instalador) y luego `py -3.11 -m venv .venv` |
| **Linux** | Generalmente viene por defecto. Si no: `sudo apt install python3.11 python3.11-venv` |

---

## 🚀 Uso

### 1. Armá tu archivo de links

```bash
cp links.example.txt ~/Music/links.txt
vim ~/Music/links.txt
```

Ejemplo de `links.txt`:

```text
# Canciones sueltas
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/jNQXAC9IVRw          Rick Astley clásico
dQw4w9WgXcQ                            # ID solo también funciona

# Mezclando canales
https://www.youtube.com/watch?v=9bZkp7q19f0   Gangnam Style
https://www.youtube.com/watch?v=kJQP7kiw5Fk   Despacito
```

Reglas:
- Una URL por línea.
- Líneas con `#` o `//` son comentarios, se ignoran.
- Líneas vacías se ignoran.
- Acepta URL completa, `youtu.be/<id>`, o solo el ID de 11 caracteres.
- Texto después de la URL (separado por espacio o tab) se guarda como descripción opcional.
- URLs duplicadas se deduplican automáticamente (preservando la primera aparición).

### 2. Validar el archivo

```bash
yt-links-mp3 validate ~/Music/links.txt
```

Muestra cuántos links válidos hay, sin descargar nada. Útil para detectar typos antes de gastar ancho de banda.

### 3. Descargar

```bash
# Básico: descarga a ~/Music/Downloads/
yt-links-mp3 download ~/Music/links.txt

# Carpeta de salida personalizada
yt-links-mp3 download ~/Music/links.txt -o ~/Music/MiCarpeta

# Previsualizar (dry-run)
yt-links-mp3 download ~/Music/links.txt --dry-run

# Forzar re-descarga (ignora lo que ya está)
yt-links-mp3 download ~/Music/links.txt --force

# Concurrencia (default: 3)
yt-links-mp3 download ~/Music/links.txt --concurrency 5

# Reintentos en errores transitorios (default: 3 con backoff 1s, 5s, 15s)
# Configurable vía config.yaml: max_retries, retry_backoff_base

# Reintentar solo los que fallaron la vez pasada
yt-links-mp3 download ~/Music/links.txt.failed
```

---

## ⚙️ Configuración (`config.yaml`)

```yaml
# Carpeta de salida (todos los MP3s se guardan acá, sin subcarpetas)
output_dir: ~/Music/Downloads

# Formato y calidad de audio
audio_format: mp3
audio_quality: 320  # kbps — máximo para MP3 (CBR)

# Descarga
concurrency: 3
force: false
dry_run: false

# Reintentos en errores transitorios (network, 5xx, timeout).
# Errores permanentes (404, privado, eliminado, age-restricted) no se reintentan.
max_retries: 3
# Backoff exponencial en segundos: base * 5^(attempt-1).
# Default 1.0 → 1s, 5s, 15s entre intentos.
retry_backoff_base: 1.0

# Portada embebida en el MP3 (ID3v2.4 cover art)
embed_thumbnail: true

# Template para el nombre del archivo.
# Placeholders: {track_number} {artist} {title} {video_id} {ext}
# Formato de padding: {track_number:02d} → 01, 02, 03…
filename_template: "{track_number:02d} - {artist} - {title}.{ext}"

# Regex (case-insensitive) a borrar del título al limpiar
cleanup_patterns:
  - '\(official video\)'
  - '\(official music video\)'
  - '\(official\)'
  - '\(lyric(?:s)? video\)'
  - '\(lyric(?:s)?\)'
  - '\(lyrics?\)'
  - '\(hd\)'
  - '\bhd\b'
  - 'official video'
  - 'music video'
  - '\blyrics?\b'
```

### Override de metadatos vía `links.txt`

Podés sobreescribir artista/título agregando un hint después de la URL:

```
https://youtu.be/dQw4w9WgXcQ   Rick Astley/Never Gonna Give You Up
https://youtu.be/jNQXAC9IVRw   Artist - Custom Title
```

Formatos de hint aceptados: `Artist/Title` o `Artist - Title`.

---

## 📁 Estructura resultante

Por defecto los archivos se guardan en `~/Music/Downloads/` con el patrón `{NN} - {artist} - {title}.mp3`:

```
~/Music/Downloads/
├── 01 - Rick Astley - Never Gonna Give You Up.mp3
├── 02 - PSY - Gangnam Style.mp3
└── 03 - Luis Fonsi - Despacito.mp3
```

- `{NN}` es el número de track, asignado incrementalmente según el orden en `links.txt`.
- Los títulos se limpian automáticamente: se borra `Official Video`, `HD`, `(Lyric)`, etc.
- La portada del video se embebe en cada MP3 (ID3v2.4 cover art).
- Si un archivo con el mismo nombre ya existe, se omite (skip). Usar `--force` para re-descargar.

---

## 🔁 Workflow típico

```bash
# Día 1: armás tu archivo de links curado
vim ~/Music/links.txt
# Pegás URLs a mano, con descripciones opcionales

# Día 1: descargás todo
yt-links-mp3 download ~/Music/links.txt

# Días siguientes: agregás más links y volvés a correr
vim ~/Music/links.txt
yt-links-mp3 download ~/Music/links.txt
# → sin --force respeta los que ya están descargados (skip automático por nombre)

# Si algo falló (video privado, geo-block, etc.):
cat ~/Music/links.txt.failed     # solo los que fallaron
yt-links-mp3 download ~/Music/links.txt.failed  # reintenta esos
```

---

## 🧪 Tests

```bash
# Con el venv activado:
pytest                              # corre todos los tests
pytest tests/test_linklist.py -v    # solo el parser de links
```

Estado actual: **144/144 tests pasando**. Desde v0.1: **+19 tests** = 17 nuevos en `test_cli.py` (info command polish: `info <URL>` muestra estado "ya descargado", `_format_duration` maneja horas con formato `H:MM:SS`, `info <archivo>` concurrente con `ThreadPoolExecutor`) + 2 nuevos en `test_downloader.py` (preservación de orden original en `links.txt.failed`).

Distribución: `test_linklist.py` 17, `test_metadata.py` 36, `test_paths.py` 18, `test_config.py` 5, `test_downloader.py` 20, `test_cli.py` 32, `test_cache.py` 16.

## 🔧 Makefile

```bash
make install    # crea venv e instala deps de dev
make test       # corre pytest
make lint       # ruff check
make lint-fix   # ruff check --fix
make format     # ruff format
make run ARGS='download links.txt'  # ejecuta el CLI
make clean      # borra caches
```

CI con GitHub Actions (`.github/workflows/tests.yml`): lint + tests en matrix Python 3.10/3.11/3.12. Pre-commit hooks (`.pre-commit-config.yaml`): ruff lint + format.

## 🔍 Comando `info`

```bash
# De un solo link (URL completa o ID de 11 chars)
yt-links-mp3 info "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
yt-links-mp3 info dQw4w9WgXcQ

# De un archivo completo (tabla con todos los links)
yt-links-mp3 info ~/Music/links.txt
```

Muestra título, artista, duración y si ya está descargado, sin tocar disco.

## 💾 Cache de metadata

Para evitar llamadas repetidas a YouTube (lento, rate-limited), `yt-links-mp3` cachea la metadata por `video_id` en:

- `$XDG_CACHE_HOME/yt-links-mp3/metadata.json` (si la variable está definida)
- `~/.cache/yt-links-mp3/metadata.json` (si no)

**TTL por defecto:** 7 días. Para modificarlo, editá `config.yaml`:

```yaml
cache_path: ~/.cache/yt-links-mp3/metadata.json
cache_ttl_seconds: 604800   # 7 días. null = sin expiración. 0 = expira siempre.
```

> Nota: `cache_ttl_seconds: 0` significa que la entrada expira al toque (porque cualquier tiempo transcurrido > 0). Solo `null` (sin valor, o línea comentada) significa "sin expiración".

> El cache se aplica en `info` y en `download` (cuando vuelve a fetchear metadata de un link conocido). La primera corrida llena el cache; las siguientes son instantáneas.

## 🌐 Sitios soportados

El parser y el downloader son agnósticos del sitio — usan `yt-dlp`, que soporta [más de 1500 sitios](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md). Algunos comunes:

| Sitio | Soporte | Notas |
|-------|---------|-------|
| YouTube | ✅ | Sitio primario. URLs `youtube.com/watch?v=ID`, `youtu.be/ID`, `/shorts/ID`, o ID solo. |
| SoundCloud | ✅ | Cualquier URL de track público. |
| Bandcamp | ✅ | URLs `artist.bandcamp.com/track/...`. |
| Vimeo | ✅ | URLs `vimeo.com/<id>`. |
| Cualquier URL `http(s)://` | ✅ | Se intenta con el extractor correspondiente de yt-dlp. |

Ejemplo de archivo mixto:

```text
# YouTube
https://www.youtube.com/watch?v=dQw4w9WgXcQ
dQw4w9WgXcQ                              # ID solo
https://youtu.be/jNQXAC9IVRw             # URL corta
https://www.youtube.com/shorts/abc12345678

# Otros sitios
https://soundcloud.com/artist/track-name
https://artist.bandcamp.com/track/song
```

> Las URLs no-YouTube no se deduplican por video_id (porque no hay uno corto universal) — se deduplican por URL completa.

---

## ⚖️ Aviso legal

Este proyecto es solo para uso personal. Respeta los derechos de autor y los Términos de Servicio de YouTube. No distribuyas el contenido descargado.

---

## 📄 Licencia

Ver [`LICENSE`](./LICENSE) para el texto completo.

MIT © 2026 Jonatan Alpirez
