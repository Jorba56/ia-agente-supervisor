#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║          AGENTE GEMINI — Asistente Total para tu Proyecto        ║
║                    Spring Boot 4.x + Java 21                     ║
╚══════════════════════════════════════════════════════════════════╝

MODOS DISPONIBLES:
  tests        → Genera tests unitarios JUnit 5 + Mockito
  docs         → Genera documentación Javadoc y Markdown
  analisis     → Analiza bugs, SOLID, code smells
  refactor     → Sugiere y aplica refactoring
  readme       → Genera README.md completo del proyecto
  dockerfile   → Genera o mejora Dockerfile y docker-compose
  sql          → Genera scripts SQL (migraciones, datos de prueba)
  frontend     → Genera código JS/HTML para consumir tus endpoints
  seguridad    → Audita vulnerabilidades de seguridad
  chat         → Modo conversacional libre sobre tu proyecto

USO:
  py agente_gemini.py --modo tests --clase EvaluacionServiceImpl --microservicio examenes-service
  py agente_gemini.py --modo chat
  py agente_gemini.py --modo readme
  py agente_gemini.py --modo analisis --todo --microservicio examenes-service
"""

import os
import sys
import re
import subprocess
import json
import argparse
import requests
try:
    import readline  # Solo disponible en Linux/Mac
except ImportError:
    pass  # En Windows no está disponible, no pasa nada
from pathlib import Path
from datetime import datetime

# ════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ════════════════════════════════════════════════════════════
GEMINI_API_KEY  = os.environ.get("GOOGLE_API_KEY")
GEMINI_MODEL    = "gemini-3.1-pro-preview"   # flash = rápido y barato; pro = más potente
GEMINI_URL      = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)
RUTA_PROYECTO   = r"C:\Users\6003609\Downloads\sprint\sprintDef\generador-examenes-back"
MAX_TOKENS_CTX  = 900_000   # Límite seguro para contexto (Gemini soporta 1M)
TEMPERATURA     = 0.2        # Bajo = más determinista para código
MAX_OUT_TOKENS  = 8192

# Extensiones que el agente puede leer
EXTENSIONES_CODIGO = {
    ".java", ".xml", ".properties", ".yml", ".yaml",
    ".sql", ".json", ".js", ".ts", ".html", ".css",
    ".md", ".txt", ".sh", ".dockerfile", ".env", ".py"
}

# Carpetas que siempre ignoramos
CARPETAS_IGNORAR = {"target", "node_modules", ".git", ".idea", "__pycache__", ".mvn"}

# Colores ANSI para la terminal
C = {
    "reset":  "\033[0m",
    "bold":   "\033[1m",
    "verde":  "\033[92m",
    "azul":   "\033[94m",
    "cyan":   "\033[96m",
    "amarillo": "\033[93m",
    "rojo":   "\033[91m",
    "gris":   "\033[90m",
    "magenta": "\033[95m",
}

def color(texto: str, *colores: str) -> str:
    prefix = "".join(C.get(c, "") for c in colores)
    return f"{prefix}{texto}{C['reset']}"


# ════════════════════════════════════════════════════════════
#  LECTURA DE ARCHIVOS
# ════════════════════════════════════════════════════════════

def debe_ignorar(ruta: Path) -> bool:
    """True si la ruta está en una carpeta que debemos ignorar."""
    partes = set(ruta.parts)
    return bool(partes & CARPETAS_IGNORAR)


def leer_archivo(ruta: Path) -> str | None:
    """Lee un archivo de texto. Devuelve None si falla."""
    try:
        return ruta.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def buscar_archivo(nombre: str, microservicio: str = None, solo_main: bool = True) -> Path | None:
    """Busca un archivo por nombre (con o sin extensión) en el proyecto."""
    ruta_base = Path(RUTA_PROYECTO)
    if microservicio:
        ruta_base = ruta_base / microservicio

    # Si no tiene extensión, prueba con .java primero

    nombres = [nombre + ".java", nombre + ".py"] if "." not in nombre else [nombre]

    for n in nombres:
        for archivo in ruta_base.rglob(n):
            if debe_ignorar(archivo):
                continue
            if solo_main and ("test" in str(archivo).lower()):
                continue
            return archivo

    return None


def buscar_todos(microservicio: str = None, extensiones: set = None, solo_main: bool = True) -> list[Path]:
    """Busca todos los archivos de código en el proyecto."""
    if extensiones is None:
        extensiones = EXTENSIONES_CODIGO

    ruta_base = Path(RUTA_PROYECTO)
    if microservicio:
        ruta_base = ruta_base / microservicio

    archivos = []
    for archivo in ruta_base.rglob("*"):
        if not archivo.is_file():
            continue
        if debe_ignorar(archivo):
            continue
        if archivo.suffix not in extensiones:
            continue
        ruta_str = str(archivo)
        if solo_main and archivo.suffix == ".java" and ("src\\main" not in ruta_str and "src/main" not in ruta_str):
            continue
        archivos.append(archivo)

    return sorted(archivos)


def contexto_clase(archivo: Path, microservicio: str = None) -> str:
    """Construye contexto inteligente leyendo solo las clases relacionadas."""
    codigo = leer_archivo(archivo)
    if not codigo:
        return ""

    # Detecta imports del propio proyecto
    imports = re.findall(r'import com\.jorge\.[^;]+;', codigo)
    clases_usadas = list(set(imp.split(".")[-1].replace(";", "").strip() for imp in imports))

    ruta_base = Path(RUTA_PROYECTO)
    if microservicio:
        ruta_base = ruta_base / microservicio

    partes = []
    encontradas = []
    for nombre in clases_usadas:
        for f in ruta_base.rglob(f"{nombre}.java"):
            if debe_ignorar(f):
                continue
            contenido = leer_archivo(f)
            if contenido:
                rel = f.relative_to(Path(RUTA_PROYECTO))
                partes.append(f"// === {rel} ===\n{contenido}")
                encontradas.append(nombre)
                break

    if encontradas:
        print(color(f"  📎 Contexto: {', '.join(encontradas)}", "gris"))

    return "\n\n".join(partes)


def contexto_proyecto_completo(microservicio: str = None, extensiones: set = None) -> str:
    """Lee TODO el proyecto y lo concatena respetando el límite de tokens."""
    if extensiones is None:
        extensiones = {".java"}

    archivos = buscar_todos(microservicio, extensiones)
    partes = []
    total_chars = 0
    limite_chars = MAX_TOKENS_CTX * 3  # ~3 chars por token

    for archivo in archivos:
        contenido = leer_archivo(archivo)
        if not contenido:
            continue
        rel = archivo.relative_to(Path(RUTA_PROYECTO))
        bloque = f"// === {rel} ===\n{contenido}"
        if total_chars + len(bloque) > limite_chars:
            print(color(f"  ⚠️  Límite de contexto alcanzado. Omitiendo el resto.", "amarillo"))
            break
        partes.append(bloque)
        total_chars += len(bloque)

    print(color(f"  📁 Contexto: {len(partes)} archivos ({total_chars // 1000}K chars)", "gris"))
    return "\n\n".join(partes)


# ════════════════════════════════════════════════════════════
#  LLAMADA A GEMINI
# ════════════════════════════════════════════════════════════

def llamar_gemini(prompt: str, historial: list = None) -> str:
    """Llama a la API de Gemini. Soporta modo conversacional con historial."""
    if historial:
        # Modo chat: incluye el historial de mensajes anteriores
        contents = historial + [{"role": "user", "parts": [{"text": prompt}]}]
    else:
        contents = [{"role": "user", "parts": [{"text": prompt}]}]

    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": TEMPERATURA,
            "maxOutputTokens": MAX_OUT_TOKENS,
        }
    }

    try:
        resp = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=180
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    except requests.exceptions.Timeout:
        print(color("  ❌ Timeout — Gemini tardó más de 3 minutos", "rojo"))
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        msg = e.response.text if e.response else str(e)
        print(color(f"  ❌ Error HTTP: {msg[:300]}", "rojo"))
        sys.exit(1)
    except (KeyError, IndexError):
        raw = resp.text if 'resp' in locals() else "sin respuesta"
        print(color(f"  ❌ Respuesta inesperada: {raw[:300]}", "rojo"))
        sys.exit(1)


# ════════════════════════════════════════════════════════════
#  LIMPIEZA Y GUARDADO
# ════════════════════════════════════════════════════════════

def limpiar_codigo(texto: str) -> str:
    """Extrae el código Java del bloque markdown si Gemini lo envuelve."""
    texto = texto.strip()
    match = re.search(r'```(?:java|sql|javascript|js|html|bash|sh|yaml|yml|xml|json)?\s*\n(.*?)```', texto, re.DOTALL)
    if match:
        return match.group(1).strip()
    return texto


def ruta_salida(archivo: Path, modo: str, sufijo: str = None) -> Path:
    """Calcula la ruta donde guardar el archivo generado."""
    ruta_str = str(archivo)

    modos_test = {"tests"}
    modos_doc  = {"docs", "analisis", "seguridad", "readme"}

    if modo in modos_test:
        ruta_test = ruta_str.replace("src\\main\\java", "src\\test\\java") \
            .replace("src/main/java",  "src/test/java")
        nombre = archivo.stem + "Test.java"
        return Path(ruta_test).parent / nombre

    elif modo in modos_doc:
        ext = ".md"
        suf = sufijo or f"_{modo}"
        return archivo.parent / f"{archivo.stem}{suf}{ext}"

    else:
        # Usa la extensión original del archivo (.py o .java)
        ext = sufijo or f"_{modo}{archivo.suffix}"
        return archivo.parent / (archivo.stem + ext)


def guardar(ruta: Path, contenido: str):
    """Guarda contenido en disco creando carpetas si es necesario."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")


# ════════════════════════════════════════════════════════════
#  PROMPTS POR MODO
# ════════════════════════════════════════════════════════════

SYSTEM_BASE = """
Eres un experto Senior en Java 21, Spring Boot 4.x, Docker, JUnit 5, Mockito y buenas prácticas de desarrollo.
El proyecto es un sistema de gestión de exámenes con arquitectura de microservicios (Spring Cloud, Eureka, API Gateway).
Responde siempre en español. Sé preciso, concreto y genera código que compile sin errores.
"""

def prompt_tests(nombre: str, codigo: str, ctx: str) -> str:
    return f"""{SYSTEM_BASE}

=== CONTEXTO DEL PROYECTO ===
{ctx}

=== CLASE A TESTEAR: {nombre} ===
```java
{codigo}
```

TAREA: Genera tests unitarios completos y exhaustivos.

REQUISITOS:
- JUnit 5: @Test, @ExtendWith(MockitoExtension.class), @BeforeEach
- Mockito: @Mock, @InjectMocks, when(...).thenReturn(...), verify(...)
- Cubre: happy path, valores nulos, listas vacías, excepciones
- Nombres: deberia_[resultado]_cuando_[condicion]()
- Imports completos desde el primer package
- Sin explicaciones — solo código Java listo para compilar
"""


def prompt_docs(nombre: str, codigo: str, ctx: str) -> str:
    return f"""{SYSTEM_BASE}

=== CONTEXTO DEL PROYECTO ===
{ctx}

=== CLASE: {nombre} ===
```java
{codigo}
```

TAREA: Genera documentación completa en Markdown.

INCLUYE:
1. Descripción de la clase y su responsabilidad en el sistema
2. Diagrama de dependencias (texto ASCII)
3. Tabla de métodos públicos con parámetros, retorno y descripción
4. Ejemplos de uso con código
5. Javadoc listo para copiar al archivo fuente
"""


def prompt_analisis(nombre: str, codigo: str, ctx: str) -> str:
    return f"""{SYSTEM_BASE}

=== CONTEXTO DEL PROYECTO ===
{ctx}

=== CLASE: {nombre} ===
```java
{codigo}
```

TAREA: Análisis profesional de código.

SECCIONES:
1. **RESUMEN** — Qué hace y su rol en el sistema
2. **PUNTOS FUERTES** — Qué está bien
3. **BUGS POTENCIALES** — Problemas que pueden causar errores en producción
4. **CODE SMELLS** — Violaciones de SOLID, DRY, KISS
5. **MEJORAS** — Código refactorizado con explicación
6. **TESTS PRIORITARIOS** — Los 3 casos más críticos a cubrir
"""


def prompt_refactor(nombre: str, codigo: str, ctx: str) -> str:
    return f"""{SYSTEM_BASE}

=== CONTEXTO DEL PROYECTO ===
{ctx}

=== CLASE ORIGINAL: {nombre} ===
```java
{codigo}
```

TAREA: Refactoriza la clase mejorando:
- Legibilidad y nomenclatura
- Aplicación de principios SOLID
- Manejo de excepciones
- Eliminación de código duplicado
- Rendimiento donde sea posible

Genera la clase completa refactorizada lista para reemplazar la original.
Añade comentarios explicando cada cambio importante.
"""


def prompt_readme(ctx: str) -> str:
    return f"""{SYSTEM_BASE}

=== CÓDIGO COMPLETO DEL PROYECTO ===
{ctx}

TAREA: Genera un README.md profesional y completo para este proyecto.

INCLUYE:
1. Título y descripción del proyecto
2. Arquitectura (diagrama ASCII de microservicios)
3. Tecnologías usadas con versiones
4. Requisitos previos
5. Instalación y configuración paso a paso
6. Variables de entorno necesarias
7. Cómo ejecutar con Docker Compose
8. Endpoints principales de cada microservicio (tabla)
9. Estructura de carpetas
10. Cómo ejecutar los tests
11. Contribución y licencia
"""


def prompt_dockerfile(ctx: str) -> str:
    return f"""{SYSTEM_BASE}

=== PROYECTO ===
{ctx}

TAREA: Analiza el proyecto y genera:
1. Un Dockerfile optimizado para producción para cada microservicio detectado
2. Un docker-compose.yml completo con todos los servicios
3. Un .dockerignore apropiado
4. Explicación de las decisiones tomadas

Usa multi-stage build para minimizar el tamaño de las imágenes.
"""


def prompt_sql(ctx: str, descripcion: str) -> str:
    return f"""{SYSTEM_BASE}

=== PROYECTO ===
{ctx}

TAREA: {descripcion}

Genera scripts SQL para MySQL 8.x.
Incluye comentarios explicativos.
Usa transacciones donde sea apropiado.
"""


def prompt_frontend(ctx: str, descripcion: str) -> str:
    return f"""{SYSTEM_BASE}

=== PROYECTO (BACKEND) ===
{ctx}

TAREA: {descripcion}

Genera código JavaScript/HTML moderno.
Usa fetch API con async/await.
Incluye manejo de errores y loading states.
Usa el token JWT del localStorage para autenticación.
"""


def prompt_seguridad(nombre: str, codigo: str, ctx: str) -> str:
    return f"""{SYSTEM_BASE}

=== CONTEXTO ===
{ctx}

=== CLASE: {nombre} ===
```java
{codigo}
```

TAREA: Auditoría de seguridad.

ANALIZA:
1. **Inyección SQL** — Queries sin parametrizar
2. **Autenticación/Autorización** — Endpoints sin proteger, roles incorrectos
3. **Exposición de datos** — DTOs que exponen campos sensibles
4. **JWT** — Validación correcta del token
5. **CORS** — Configuración demasiado permisiva
6. **Dependencias** — Versiones con vulnerabilidades conocidas
7. **Secretos** — Credenciales hardcodeadas

Para cada problema: gravedad (CRÍTICO/ALTO/MEDIO/BAJO), descripción y solución.
"""


# ════════════════════════════════════════════════════════════
#  MODOS DE EJECUCIÓN
# ════════════════════════════════════════════════════════════

def modo_clase(nombre: str, modo: str, microservicio: str = None):
    """Procesa un modo que opera sobre una clase concreta."""
    print(f"\n{color('🔍 Buscando', 'cyan')} {color(nombre + '.java', 'bold')}...")

    archivo = buscar_archivo(nombre, microservicio)
    if not archivo:
        print(color(f"  ❌ No encontrado: {nombre}", "rojo"))
        sys.exit(1)

    rel = archivo.relative_to(Path(RUTA_PROYECTO))
    print(color(f"  ✅ {rel}", "verde"))

    codigo = leer_archivo(archivo)
    print(f"  📖 Leyendo contexto relacionado...")
    ctx = contexto_clase(archivo, microservicio)

    print(f"  🤖 Enviando a Gemini...")

    prompts = {
        "tests":     prompt_tests(nombre, codigo, ctx),
        "docs":      prompt_docs(nombre, codigo, ctx),
        "analisis":  prompt_analisis(nombre, codigo, ctx),
        "refactor":  prompt_refactor(nombre, codigo, ctx),
        "seguridad": prompt_seguridad(nombre, codigo, ctx),
    }

    prompt = prompts.get(modo)
    if not prompt:
        print(color(f"  ❌ Modo '{modo}' no soportado para clases individuales", "rojo"))
        sys.exit(1)

    respuesta = llamar_gemini(prompt)

    # Limpia código si es necesario
    if modo in {"tests", "refactor"}:
        respuesta = limpiar_codigo(respuesta)

    salida = ruta_salida(archivo, modo)
    guardar(salida, respuesta)

    print(color(f"\n✅ Generado:", "verde", "bold"), color(str(salida), "cyan"))
    print(color(f"   {len(respuesta):,} caracteres", "gris"))


def modo_todo(modo: str, microservicio: str = None):
    """Procesa todas las clases del microservicio."""
    archivos = buscar_todos(microservicio)

    if not archivos:
        print(color("❌ No se encontraron archivos compatibles", "rojo"))
        sys.exit(1)

    print(f"\n{color('📦', 'cyan')} Procesando {color(str(len(archivos)), 'bold')} archivos...\n")

    ok, fail = 0, 0
    inicio = datetime.now()

    for i, archivo in enumerate(archivos, 1):
        nombre = archivo.stem
        print(f"{color(f'[{i}/{len(archivos)}]', 'gris')} {color(nombre, 'bold')}...")

        try:
            codigo = leer_archivo(archivo)
            ctx    = contexto_clase(archivo, microservicio)

            prompts = {
                "tests":    prompt_tests(nombre, codigo, ctx),
                "analisis": prompt_analisis(nombre, codigo, ctx),
                "docs":     prompt_docs(nombre, codigo, ctx),
                "seguridad":prompt_seguridad(nombre, codigo, ctx),
            }
            prompt = prompts.get(modo)
            if not prompt:
                continue

            respuesta = llamar_gemini(prompt)
            if modo in {"tests", "refactor"}:
                respuesta = limpiar_codigo(respuesta)

            salida = ruta_salida(archivo, modo)
            guardar(salida, respuesta)
            print(color(f"  ✅ {salida.name}", "verde"))
            ok += 1

        except Exception as e:
            print(color(f"  ❌ {e}", "rojo"))
            fail += 1

    dur = (datetime.now() - inicio).seconds
    print(f"\n{'═'*50}")
    print(color(f"✅ Exitosos: {ok}  ❌ Fallidos: {fail}  ⏱ {dur}s", "bold"))
    print(f"{'═'*50}")


def modo_readme(microservicio: str = None):
    """Genera README.md para el proyecto."""
    print(f"\n{color('📖 Leyendo proyecto completo...', 'cyan')}")
    ctx = contexto_proyecto_completo(microservicio, {".java", ".yml", ".properties", ".xml"})

    print(f"  🤖 Generando README...")
    respuesta = llamar_gemini(prompt_readme(ctx))

    salida = Path(RUTA_PROYECTO) / (microservicio or "") / "README.md"
    guardar(salida, respuesta)
    print(color(f"\n✅ README generado: {salida}", "verde", "bold"))


def modo_dockerfile_cmd(microservicio: str = None):
    """Genera Dockerfile y docker-compose."""
    print(f"\n{color('🐳 Leyendo proyecto...', 'cyan')}")
    ctx = contexto_proyecto_completo(microservicio, {".java", ".yml", ".properties", ".xml"})

    print(f"  🤖 Generando configuración Docker...")
    respuesta = llamar_gemini(prompt_dockerfile(ctx))

    salida = Path(RUTA_PROYECTO) / "docker_generado.md"
    guardar(salida, respuesta)
    print(color(f"\n✅ Docker config generada: {salida}", "verde", "bold"))


def modo_sql_cmd(descripcion: str, microservicio: str = None):
    """Genera scripts SQL."""
    print(f"\n{color('🗄️  Leyendo proyecto...', 'cyan')}")
    ctx = contexto_proyecto_completo(microservicio, {".java", ".sql", ".properties"})

    print(f"  🤖 Generando SQL...")
    respuesta = llamar_gemini(prompt_sql(ctx, descripcion))
    respuesta = limpiar_codigo(respuesta)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    salida = Path(RUTA_PROYECTO) / f"script_{ts}.sql"
    guardar(salida, respuesta)
    print(color(f"\n✅ SQL generado: {salida}", "verde", "bold"))


def modo_frontend_cmd(descripcion: str, microservicio: str = None):
    """Genera código frontend."""
    print(f"\n{color('🌐 Leyendo controladores...', 'cyan')}")
    archivos_ctrl = [f for f in buscar_todos(microservicio) if "Controller" in f.name]

    partes = []
    for f in archivos_ctrl:
        c = leer_archivo(f)
        if c:
            rel = f.relative_to(Path(RUTA_PROYECTO))
            partes.append(f"// === {rel} ===\n{c}")
    ctx = "\n\n".join(partes)

    print(f"  🤖 Generando frontend...")
    respuesta = llamar_gemini(prompt_frontend(ctx, descripcion))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = ".html" if "html" in descripcion.lower() else ".js"
    salida = Path(RUTA_PROYECTO) / f"frontend_generado_{ts}{ext}"
    guardar(salida, respuesta)
    print(color(f"\n✅ Frontend generado: {salida}", "verde", "bold"))


def modo_chat(microservicio: str = None):
    """Modo conversacional interactivo sobre el proyecto."""
    print(f"\n{color('╔══════════════════════════════════════╗', 'cyan')}")
    print(f"{color('║   💬 MODO CHAT — Agente Gemini       ║', 'cyan')}")
    print(f"{color('╚══════════════════════════════════════╝', 'cyan')}")
    print(color("Escribe tu pregunta sobre el proyecto. 'salir' para terminar.", "gris"))
    print(color("Comandos: /contexto  /limpiar  /guardar  /archivo <nombre>", "gris"))
    print()

    # Carga contexto del proyecto una sola vez
    print(color("📖 Cargando contexto del proyecto...", "amarillo"))
    ctx = contexto_proyecto_completo(microservicio, {".java", ".properties", ".yml"})

    system_msg = f"""{SYSTEM_BASE}

Tienes acceso completo al siguiente proyecto:
{ctx}

Responde preguntas, genera código, explica, sugiere mejoras.
Cuando generes código Java, envuélvelo en bloques ```java ... ```.
"""

    historial = [
        {"role": "user",  "parts": [{"text": system_msg}]},
        {"role": "model", "parts": [{"text": "Entendido. Tengo el contexto completo del proyecto cargado. ¿En qué puedo ayudarte?"}]}
    ]

    conversacion = []
    print(color("✅ Contexto cargado. ¡Listo!\n", "verde"))

    while True:
        try:
            entrada = input(color("Tú → ", "cyan", "bold")).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{color('👋 ¡Hasta luego!', 'verde')}")
            break

        if not entrada:
            continue

        if entrada.lower() in {"salir", "exit", "quit"}:
            print(color("👋 ¡Hasta luego!", "verde"))
            break

        if entrada == "/limpiar":
            historial = historial[:2]  # Mantiene solo el contexto inicial
            print(color("🧹 Historial limpiado.", "amarillo"))
            continue

        if entrada == "/contexto":
            print(color(f"📁 Contexto activo: {len(ctx):,} chars | {len(historial)} turnos", "gris"))
            continue

        if entrada.startswith("/archivo "):
            nombre = entrada[9:].strip()
            archivo = buscar_archivo(nombre, microservicio)
            if archivo:
                contenido = leer_archivo(archivo)
                print(color(f"📄 {archivo.relative_to(Path(RUTA_PROYECTO))} ({len(contenido):,} chars)", "verde"))
                # Añade el archivo al contexto de la conversación
                entrada = f"Añado este archivo al contexto:\n```java\n{contenido}\n```\nConfirma que lo has recibido."
            else:
                print(color(f"❌ No encontrado: {nombre}", "rojo"))
                continue

        if entrada == "/guardar":
            if conversacion:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                salida = Path(RUTA_PROYECTO) / f"chat_{ts}.md"
                md = "\n\n".join(f"**{'Tú' if r=='user' else 'Gemini'}:** {t}" for r, t in conversacion)
                guardar(salida, md)
                print(color(f"💾 Guardado en: {salida}", "verde"))
            else:
                print(color("No hay conversación para guardar.", "amarillo"))
            continue

        # Llama a Gemini con el historial
        print(color("  🤖 Pensando...", "gris"), end="\r")
        respuesta = llamar_gemini(entrada, historial)

        # Actualiza historial
        historial.append({"role": "user",  "parts": [{"text": entrada}]})
        historial.append({"role": "model", "parts": [{"text": respuesta}]})
        conversacion.append(("user", entrada))
        conversacion.append(("model", respuesta))

        print(f"\n{color('Gemini →', 'magenta', 'bold')} {respuesta}\n")



# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════

BANNER = f"""
{color('╔══════════════════════════════════════════════════════╗', 'cyan')}
{color('║       AGENTE GEMINI — Asistente Total Código          ║', 'cyan', 'bold')}
{color('╚══════════════════════════════════════════════════════╝', 'cyan')}
"""

def main():
    parser = argparse.ArgumentParser(
        description="Agente Gemini — Asistente total para tu proyecto Java",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EJEMPLOS:
  py agente_gemini.py --modo tests    --clase EvaluacionServiceImpl --microservicio examenes-service
  py agente_gemini.py --modo analisis --clase ExamenController       --microservicio examenes-service
  py agente_gemini.py --modo refactor --clase ReporteServiceImpl     --microservicio examenes-service
  py agente_gemini.py --modo seguridad --clase SecurityConfig        --microservicio examenes-service
  py agente_gemini.py --modo docs     --todo  --microservicio examenes-service
  py agente_gemini.py --modo readme   --microservicio examenes-service
  py agente_gemini.py --modo dockerfile
  py agente_gemini.py --modo sql      --descripcion "Genera datos de prueba para la tabla evaluaciones"
  py agente_gemini.py --modo frontend --descripcion "Genera un formulario HTML para crear exámenes"
  py agente_gemini.py --modo chat     --microservicio examenes-service
        """
    )

    parser.add_argument("--modo", required=True,
                        choices=["tests","docs","analisis","refactor","readme","dockerfile","sql","frontend","seguridad","chat"],
                        help="Qué hacer")
    parser.add_argument("--clase",
                        help="Nombre de la clase Java (sin .java)")
    parser.add_argument("--microservicio",
                        help="Nombre del microservicio (ej: examenes-service)")
    parser.add_argument("--todo", action="store_true",
                        help="Procesar todas las clases del microservicio")
    parser.add_argument("--descripcion",
                        help="Descripción para modos sql y frontend")

    args = parser.parse_args()

    print(BANNER)
    print(color(f"  Modelo:  {GEMINI_MODEL}", "gris"))
    print(color(f"  Proyecto: {RUTA_PROYECTO}", "gris"))
    if args.microservicio:
        print(color(f"  Servicio: {args.microservicio}", "gris"))
    print()

    # Modos que operan sobre clases
    modos_clase = {"tests", "docs", "analisis", "refactor", "seguridad"}

    if args.modo in modos_clase:
        if args.todo:
            modo_todo(args.modo, args.microservicio)
        elif args.clase:
            modo_clase(args.clase, args.modo, args.microservicio)
        else:
            print(color("❌ Especifica --clase NombreClase o --todo", "rojo"))
            sys.exit(1)

    elif args.modo == "readme":
        modo_readme(args.microservicio)

    elif args.modo == "dockerfile":
        modo_dockerfile_cmd(args.microservicio)

    elif args.modo == "sql":
        desc = args.descripcion or "Genera script SQL de datos de prueba para todas las tablas del proyecto"
        modo_sql_cmd(desc, args.microservicio)

    elif args.modo == "frontend":
        desc = args.descripcion or "Genera una página HTML con JavaScript para consumir todos los endpoints del proyecto"
        modo_frontend_cmd(desc, args.microservicio)

    elif args.modo == "chat":
        modo_chat(args.microservicio)


if __name__ == "__main__":
    main()