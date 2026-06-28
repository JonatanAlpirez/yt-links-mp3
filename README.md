# 🎵 yt-links-mp3

Descargador de música desde YouTube a partir de un **archivo de texto con URLs** (una por línea). Convierte cada video a MP3 con `yt-dlp` + `ffmpeg`.

> Pensado para uso personal: vos armás una lista curada de links en un `.txt`, y la herramienta los descarga uno a uno. Sin login, sin scraping de playlist, sin sorpresas.

---

## ✨ Características

- Lee un archivo de texto con URLs de videos individuales de YouTube (uno por línea).
- Parser tolerante: comentarios (`#`, `//`), líneas vacías, IDs solos (`dQw4w9WgXcQ`), dedupe automático.
- Convierte cada video a MP3 con `yt-dlp` + `ffmpeg` a 320 kbps (CBR) por defecto.
- Modo dry-run para previsualizar sin escribir a disco.
- Auto-reanudación: si un link falla, se escribe a `links.txt.failed` para reintentar.
- Configuración por archivo YAML.

Roadmap y features pendientes: ver [`PLAN.md`](./PLAN.md).

---

## 🧰 Stack

| Componente            | Tecnología                                | Por qué                                                                 |
| --------------------- | ----------------------------------------- | ----------------------------------------------------------------------- |
| Descarga de video     | [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) | Mantenido, soporte de URLs individuales, selectores de formato, postprocesado. |
| Extracción de audio   | `ffmpeg`                                  | Estándar de facto para muxing/conversión.                               |
| Lenguaje              | Python 3.9+ (probado en 3.11; 3.9 deprecado por yt-dlp) | Ecosistema, scripts, CLI limpio. |
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

### 3. Requisitos de Python

Probado en Python 3.11. `pyproject.toml` declara `>=3.9` pero yt-dlp deprecó 3.9.

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

# Reintentar solo los que fallaron la vez pasada
yt-links-mp3 download ~/Music/links.txt.failed
```

---

## ⚙️ Configuración (`config.yaml`)

```yaml
# Carpeta de salida
output_dir: ~/Music/Downloads

# Formato y calidad de audio
audio_format: mp3
audio_quality: 320  # kbps — máximo para MP3 (CBR)

# Descarga
concurrency: 3
force: false
dry_run: false
```

---

## 📁 Estructura resultante

Por defecto los archivos se guardan en `~/Music/Downloads/` con el nombre `<video_id>.mp3`:

```
~/Music/Downloads/
├── dQw4w9WgXcQ.mp3
├── jNQXAC9IVRw.mp3
└── 9bZkp7q19f0.mp3
```

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
# → con --force para re-descargar todo, o sin él para respetar lo que ya está

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

Estado actual: **9/9 tests pasando** (`tests/test_linklist.py` cubre el parser de links).

---

## ⚖️ Aviso legal

Este proyecto es solo para uso personal. Respeta los derechos de autor y los Términos de Servicio de YouTube. No distribuyas el contenido descargado.

---

## 📄 Licencia

MIT
