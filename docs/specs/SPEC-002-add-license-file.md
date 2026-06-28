# SPEC-002: Agregar archivo `LICENSE` (MIT)

| Campo | Valor |
|---|---|
| **ID** | SPEC-002 |
| **Título** | El repo declara licencia MIT pero no contiene el archivo `LICENSE` |
| **Severidad** | 🟡 Media (legal/profesional, no funcional) |
| **Estado** | Draft → Ready for implementation |
| **Archivos afectados** | `LICENSE` (nuevo) |
| **Esfuerzo estimado** | 5–10 min |
| **Riesgo de regresión** | Nulo (archivo nuevo, sin código) |

---

## 1. Contexto

El proyecto declara su licencia como MIT en tres lugares:

| Lugar | Texto |
|---|---|
| `README.md:396-397` | Sección `## 📄 Licencia` con valor `MIT` |
| `pyproject.toml` | Campo `license = { text = "MIT" }` (a verificar en archivo actual) |
| `PLAN.md` | Sin referencia explícita a licencia |

**Pero el archivo `LICENSE` no existe en el repo.** Confirmado en la revisión de estructura de Phase 5 (`PLAN.md:30-58` lista todos los archivos del proyecto — `LICENSE` no aparece).

### 1.1 Por qué importa

Una licencia OSI-approved (como MIT) **solo aplica si el texto completo de la licencia está presente** en el repo. Sin el archivo `LICENSE`, los términos no son ejecutables: técnicamente el código está bajo "todos los derechos reservados" por defecto en la mayoría de jurisdicciones.

Para un proyecto personal, el impacto práctico es bajo. Pero:

- **GitHub muestra un warning** prominente: "Add a license to your project" en la barra lateral del repo.
- **Para colaboradores futuros o forks públicos**, no hay claridad legal sobre qué se puede hacer con el código.
- **Inconsistencia entre docs y realidad**: el README promete MIT, pero el archivo no existe.

### 1.2 Reproducción

```bash
$ ls LICENSE*
ls: cannot access 'LICENSE*': No such file or directory
```

---

## 2. Scope

### 2.1 Dentro de scope

- Crear el archivo `LICENSE` en la raíz del repo con el texto completo de la licencia MIT estándar.
- Actualizar `README.md` para que el link "MIT" (línea 397) apunte al archivo `LICENSE` (enlaces relativos: `[MIT](./LICENSE)`).
- (Opcional) Referenciar la licencia en `PLAN.md` sección "Estado actual".

### 2.2 Fuera de scope

- Cambiar la licencia a otra (BSD, Apache 2.0, GPL).
- Agregar headers de copyright en cada archivo `.py`.
- Configurar herramientas automatizadas de enforcement de licencia (FOSSA, Snyk, etc.).
- Agregar `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` u otros archivos de governance.

---

## 3. Solución propuesta

### 3.1 Decisión de diseño

**Elegido: crear `LICENSE` con el texto canónico de MIT + copyright del owner actual.**

Justificación:

| Alternativa | Ventaja | Desventaja |
|---|---|---|
| **MIT texto canónico** (elegido) | Estándar de facto, 1 párrafo de permisos + 1 de liability | Owner debe actualizar año manualmente |
| Link a `https://opensource.org/licenses/MIT` | No requiere mantener texto en repo | No funciona offline; GitHub no detecta automáticamente |
| Sin licencia | Nada que mantener | Legalmente "todos los derechos reservados" |

### 3.2 Formato del archivo

**Path**: `LICENSE` (sin extensión, convención estándar)

**Contenido**:

```
MIT License

Copyright (c) 2025 Jonatan Alpirez

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Notas**:
- El año (`2025`) puede ajustarse al año actual del primer commit público significativo (verificar con `git log --reverse`).
- Si el owner prefiere otro formato (nombre completo, email, organización), ajustar la línea de copyright.
- NO incluir `Copyright (c)` adicional para contribuidores — MIT no lo requiere y mantener la lista es overhead.

---

## 4. Criterios de aceptación

### 4.1 Funcionales

- [ ] Existe el archivo `LICENSE` en la raíz del repo (no en subdirectorio).
- [ ] El archivo contiene el texto canónico de MIT (verificable con `head -3 LICENSE` → debe empezar con `MIT License`).
- [ ] El archivo incluye la línea `Copyright (c) <año> Jonatan Alpirez` (o nombre legal del owner).
- [ ] `README.md:396-397` se actualiza de `MIT` a un link markdown: `Ver [`LICENSE`](./LICENSE) para detalles.`

### 4.2 No regresión

- [ ] No se modificó ningún archivo en `src/`, `tests/`, `docs/specs/`.
- [ ] Los 125 tests siguen pasando (este cambio no toca código ejecutable).
- [ ] El comando `git status` muestra solo `LICENSE` y `README.md` modificados.

### 4.3 Verificación externa

- [ ] GitHub ya no muestra el warning "Add a license" en la sidebar del repo (verificar manualmente después del push).
- [ ] `gh repo view --json licenseInfo` retorna `{"licenseInfo": {"name": "MIT License", "key": "mit"}}`.

---

## 5. Archivos a modificar

### 5.1 `LICENSE` (archivo nuevo)

Crear con el contenido exacto de §3.2.

### 5.2 `README.md`

**Líneas 395-397** (sección `## 📄 Licencia`):

```diff
- ## 📄 Licencia
-
- MIT
+ ## 📄 Licencia
+
+ Ver [`LICENSE`](./LICENSE) para el texto completo.
+
+ MIT © 2025 Jonatan Alpirez
```

(O equivalente: link al archivo + línea de copyright abreviada.)

---

## 6. Comandos de verificación

```bash
# 1. Verificar que LICENSE existe en la raíz
ls -la LICENSE
# Debe mostrar: -rw-r--r-- 1 ... LICENSE

# 2. Verificar contenido
head -3 LICENSE
# Debe mostrar: MIT License (línea vacía) Copyright (c) ...

# 3. Verificar que el archivo es texto plano, no binario
file LICENSE
# Debe mostrar: ASCII text

# 4. Verificar que el archivo se commiteó
git log --oneline -1 -- LICENSE
# Debe mostrar el commit de este spec

# 5. (Después del push) Verificar desde GitHub
gh repo view --json licenseInfo
# Debe retornar MIT
```

---

## 7. Edge cases y consideraciones

### 7.1 ¿Qué año poner en el copyright?

Opciones:
- **Año del primer commit público** (`git log --reverse --format=%ai | head -1`).
- **Año actual** (cambia con cada año calendario).
- **Rango de años** (`2024-2026`) si el repo abarca varios años.

Recomendación: usar el año del primer commit público significativo (cuando el proyecto dejó de ser personal/private). Para este proyecto, parece ser 2024 o 2025 — verificar con `git log --reverse`.

### 7.2 ¿Copyright para la organización o el individuo?

El owner es Jonatan Alpirez (individual). Si en el futuro el proyecto pasa a una organización, actualizar `LICENSE` y emitir un NOTICE file.

### 7.3 ¿Aplican los headers en cada archivo `.py`?

No es requerido por MIT. Es opcional y solo se ve en proyectos grandes (>100 archivos) donde la trazabilidad de copyright importa. Para este proyecto de ~10 archivos Python, no vale la pena.

### 7.4 ¿Afecta la licencia al contenido descargado?

**No.** La licencia MIT cubre solo el **código fuente** del CLI. El contenido descargado (MP3s) sigue siendo propiedad de sus autores originales y está sujeto a las leyes de copyright correspondientes. Esto ya está cubierto por el disclaimer en `README.md:389-391` ("Aviso legal").

---

## 8. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Año incorrecto en copyright | Baja | Cosmético | Verificar con `git log --reverse` antes de crear el archivo |
| Typo en el texto canónico MIT | Baja | Medio (legal-mente el texto debe ser exacto) | Usar copy-paste del template oficial de opensource.org, no reescribir |
| Nombre del owner incorrecto | Baja | Bajo | Confirmar nombre legal del owner |
| Link relativo roto en README | Baja | Cosmético | Verificar que `LICENSE` esté en la raíz, no en subdirectorio |

---

## 9. Checklist de cierre (para el implementador)

- [ ] Obtenido el año del primer commit (`git log --reverse --format=%ai | head -1`)
- [ ] Creado `LICENSE` con texto canónico MIT + línea de copyright
- [ ] Actualizado `README.md` sección "Licencia" con link al archivo
- [ ] Verificado: `ls LICENSE` existe, `head -3 LICENSE` muestra el formato correcto
- [ ] `pytest` sigue en 125/125 (sanity check, este spec no toca código)
- [ ] Commit con mensaje: `docs: add MIT LICENSE file`
- [ ] Push y verificación en GitHub

---

## 10. Open questions

1. **¿Vale la pena agregar un header SPDX en cada archivo Python?** → **Decisión**: fuera de scope. MIT no lo requiere y para 10 archivos es overhead innecesario.
2. **¿Deberíamos emitir un NOTICE file con atribuciones de terceros?** → **Decisión**: fuera de scope. Las dependencias (yt-dlp, click, pydantic, etc.) son MIT/BSD/etc. — sus licencias vienen con el paquete, no necesitan aparecer en el repo.
3. **¿Vale la pena agregar `copyright-holder` dinámico generado por setuptools?** → **Decisión**: no, complica el build sin beneficio.

---

## 11. Referencias

- MIT License texto canónico: https://opensource.org/licenses/MIT
- SPDX license list: https://spdx.org/licenses/
- GitHub docs sobre licencias: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
- Detección de license drift en CI: https://github.com/licensee/licensee (no se usa, solo referencia)