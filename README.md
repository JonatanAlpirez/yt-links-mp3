# 🎵 yt-links-mp3

Descargador de música desde YouTube a partir de un **archivo de texto con URLs** (una por línea). Convierte cada video a MP3 con metadatos limpios y una estructura de carpetas ordenada por artista/álbum.

> Pensado para uso personal: vos armás una lista curada de links en un `.txt`, y la herramienta los descarga uno a uno. Sin login, sin scraping de playlist, sin sorpresas.

---

## ✨ Características

- Lee un archivo de texto con URLs de videos individuales (uno por línea).
- Tolera comentarios (`#`), líneas vacías, IDs solos (`dQw4w9WgXcQ`), y dedupe automático.
- Convierte cada video a MP3 con metadatos limpios: título, artista, álbum, número de pista, año, portada.
- Nombra los archivos con un patrón consistente (basado en metadatos, no en el título del video).
- Maneja duplicados y re-descargas (skip si ya existe con la misma calidad).
- Concurrencia configurable para acelerar la descarga.
- Progreso por video y progreso global del batch.
- Modo dry-run para previsualizar qué se descargaría sin tocar disco.
- Auto-reanudación: si fallan links, los escribe a `links.txt.failed` para reintentar.

---

## 🧰 Stack

| Componente            | Tecnología                                | Por qué                                                                 |
| --------------------- | ----------------------------------------- | ----------------------------------------------------------------------- |
| Descarga de video     | [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) | Mantenido, soporte de URLs individuales, selectores de formato, postprocesado. |
| Extracción de audio   | `ffmpeg`                                  | Estándar de facto para muxing/conversión.                               |
| Lenguaje              | Python 3.11+                              | Ecosistema, scripts, CLI limpio.                                        |
| CLI                   | [`click`](https://palletsprojects.com/p/click/) | Argumentos tipados, subcomandos, experiencia pro.                     |
| Config                | `pydantic-settings` + YAML               | Validación + archivo de config legible.                                |
| Logging               | `loguru`                                  | Salida colorida en consola + archivo rotado.                            |
| Progreso              | `rich`                                    | Barras de progreso y tablas bonitas.                                    |
| Tests                 | `pytest`                                  | Estándar del ecosistema.                                                |
| Empaquetado           | `uv` o `pip` + `pyproject.toml`           | Dependencias declarativas, instalable como CLI.                         |

---

## 📦 Instalación

```bash
# 1. Dependencias de sistema
brew install ffmpeg        # macOS
# sudo apt install ffmpeg # Debian/Ubuntu

# 2. Clonar e instalar
git clone <repo-url> yt-links-mp3
cd yt-links-mp3
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

> El comando `yt-links-mp3` quedará disponible en tu shell.

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

### 4. Ver metadata sin descargar

```bash
# De un solo link
yt-links-mp3 info "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# De un archivo completo (tabla con todos)
yt-links-mp3 info ~/Music/links.txt
```

---

## ⚙️ Configuración (`config.yaml`)

```yaml
# Carpeta de salida
output_dir: ~/Music/Downloads

# Formato y calidad de audio
audio_format: mp3
audio_quality: 192  # kbps

# Descarga
concurrency: 3
skip_existing: true
force: false
dry_run: false

# Metadatos
embed_metadata: true
embed_thumbnail: true

# Plantilla de nombre (placeholders: artist, title, album, track_number, ext)
filename_template: "{artist}/{album}/{track_number:02d} - {title}.{ext}"
```

---

## 📁 Estructura resultante

```
~/Music/Downloads/
├── Rick Astley/
│   └── Whenever You Need Somebody/
│       ├── cover.jpg
│       ├── 01 - Never Gonna Give You Up.mp3
│       └── 02 - Together Forever.mp3
├── PSY/
│   └── Single/
│       └── 01 - Gangnam Style.mp3
└── Luis Fonsi/
    └── Single/
        └── 01 - Despacito.mp3
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
# → skip automático de los que ya están descargados

# Si algo falló (video privado, geo-block, etc.):
cat ~/Music/links.txt.failed     # solo los que fallaron
yt-links-mp3 download ~/Music/links.txt.failed  # reintenta esos
```

---

## ⚖️ Aviso legal

Este proyecto es solo para uso personal. Respeta los derechos de autor y los Términos de Servicio de YouTube. No distribuyas el contenido descargado.

---

## 📄 Licencia

MIT
