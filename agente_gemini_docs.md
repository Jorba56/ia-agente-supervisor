***

# Documentación Técnica: `agente_gemini.py`

## 1. Visión General y Filosofía de la Herramienta
El script `agente_gemini.py` es una herramienta construida en Python. Actúa como un "Pair Programmer" autónomo que se ejecuta directamente en la terminal del desarrollador.

A diferencia de un chatbot web estándar, este agente tiene **acceso directo de lectura y escritura al sistema de archivos local**. Su filosofía principal es la **Conciencia de Contexto (Context-Awareness)**: no solo envía una clase al LLM, sino que es capaz de leer los `imports` de esa clase, buscar las dependencias locales (interfaces, repositorios, entidades) y empaquetarlas juntas en el prompt. Esto garantiza que el LLM (Google Gemini) tenga toda la información necesaria para generar código (como tests con Mockito) que compile a la primera.

---

## 2. Flujo de Ejecución Interno (Pipeline Core)
Cuando un desarrollador ejecuta un comando, el script sigue un pipeline estricto:

1.  **Parseo de Argumentos (`argparse`):** Captura el modo de operación (`tests`, `refactor`, `seguridad`, `chat`), el microservicio objetivo y la clase específica (si aplica).
2.  **Resolución de Rutas (Pathfinding):** Escanea recursivamente el directorio del microservicio ignorando carpetas compiladas (`target`, `build`, `.git`, `.idea`) para optimizar la búsqueda.
3.  **Construcción Inteligente de Contexto:**
    *   Lee la clase principal.
    *   Extrae mediante expresiones regulares (`re`) los `import com.jorge...`.
    *   Busca esos archivos importados y los concatena al contexto para que el LLM conozca las firmas de los métodos a mockear.
4.  **Inyección de Prompt (Prompt Engineering):** Selecciona la plantilla de sistema adecuada según el modo (ej. "Eres un experto en JUnit 5 y Mockito...").
5.  **Invocación de la API (Gemini):** Realiza una petición HTTP POST a la API de Google Generative AI, controlando timeouts y límites de tokens.
6.  **Post-Procesamiento (Sanitización):** Extrae el código fuente puro de la respuesta del LLM, eliminando el formato Markdown (ej. ` ```java `) y comentarios innecesarios.
7.  **Generación de Artefactos (I/O):** Calcula la ruta de destino (traduciendo `src/main/java` a `src/test/java`), crea los directorios intermedios si no existen y guarda el archivo `.java`, `.md` o `Dockerfile`.

---

## 3. Configuración y Requisitos del Entorno

Para que el script funcione correctamente, asume una estructura de proyecto estándar de Maven/Gradle y requiere ciertas configuraciones:

| Variable / Requisito | Descripción |
| :--- | :--- |
| `GOOGLE_API_KEY` | Variable de entorno obligatoria. Clave de acceso a la API de Google Gemini. |
| **Estructura Maven** | Asume que el código fuente está en `src/main/java` y los tests deben ir en `src/test/java`. |
| **Librerías Python** | Utiliza exclusivamente la biblioteca estándar de Python (`os`, `sys`, `re`, `json`, `pathlib`, `urllib.request` o `requests`, `argparse`) para no requerir entornos virtuales complejos (`venv`). |

---

## 4. Catálogo Detallado de Funciones Internas

### 4.1. Funciones de Exploración y Contexto (File System)
*   **`buscar_archivo(nombre: str, microservicio: str, solo_main: bool) -> Path | None`**
    *   *Lógica:* Usa `pathlib.Path.rglob()` para buscar el archivo. Si `solo_main` es `True`, filtra los resultados para que la ruta contenga `src/main/java`, evitando leer clases de test antiguas.
*   **`buscar_todos(microservicio: str, extensiones: set, solo_main: bool) -> list[Path]`**
    *   *Lógica:* Recopila todos los archivos `.java`, `.yml` o `.properties` de un microservicio. Se usa para auditorías globales o para el modo chat.
*   **`contexto_clase(archivo: Path, microservicio: str) -> str`**
    *   *Lógica "Smart Context":* Lee el archivo base. Usa Regex para encontrar `import com.jorge...`. Por cada import local encontrado, llama a `buscar_archivo`, lee su contenido y lo añade al string final. Esto es vital para que Gemini sepa qué métodos tienen las interfaces inyectadas.
*   **`contexto_proyecto_completo(microservicio: str, extensiones: set) -> str`**
    *   *Lógica:* Concatena todo el código del microservicio. Implementa un contador de caracteres/tokens aproximado para truncar el texto si supera el límite de la ventana de contexto de Gemini (ej. 1M tokens en Gemini 1.5 Pro).

### 4.2. Funciones de Interacción con IA y Sanitización
*   **`llamar_gemini(prompt: str, historial: list) -> str`**
    *   *Lógica:* Construye el payload JSON requerido por la API de Google. Gestiona la memoria inyectando el `historial` previo (útil en el modo chat). Maneja excepciones de red y parsea la respuesta JSON.
*   **`limpiar_codigo(texto: str) -> str`**
    *   *Lógica:* Los LLMs suelen responder con explicaciones y bloques de código (ej. `Aquí tienes tu test:\n```java\n...\n```\nEspero que sirva.`). Esta función usa Regex (`r"```(?:java|xml|sql|dockerfile)?(.*?)```"`) para extraer *únicamente* el código, permitiendo que el archivo guardado compile directamente.

### 4.3. Funciones de Generación de Artefactos (I/O)
*   **`ruta_salida(archivo: Path, modo: str, sufijo: str) -> Path`**
    *   *Lógica de Mapeo:* Si el modo es `tests`, reemplaza la subcadena `src/main/java` por `src/test/java` en la ruta absoluta, y añade el sufijo `Test.java` al nombre del archivo. Si el modo es `documentacion`, puede cambiar la extensión a `.md`.
*   **`guardar(ruta: Path, contenido: str) -> None`**
    *   *Lógica:* Verifica si el directorio padre existe (`ruta.parent.mkdir(parents=True, exist_ok=True)`). Escribe el archivo en modo texto con codificación UTF-8.

---

## 5. Modos de Operación (Ingeniería de Prompts)

El script inyecta diferentes "System Prompts" dependiendo del argumento `--modo` pasado por CLI:

| Modo CLI            | Prompt del Sistema (Resumen)                                                                                                                                                                      | Acción de Salida |
|:--------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| :--- |
| `--modo tests`      | "Eres un experto en JUnit 5 y Mockito. Genera tests unitarios cubriendo casos de éxito, excepciones y edge cases. Usa `@ExtendWith(MockitoExtension.class)`. No expliques, solo devuelve código." | Guarda en `src/test/java/.../*Test.java` |
| `--modo refactor`   | "Eres un Arquitecto Java Senior. Refactoriza esta clase aplicando principios SOLID, Clean Code y características de Java 21 (Records, Pattern Matching). Mantén la funcionalidad exacta."         | Sobrescribe el archivo original o crea un `*Refactored.java` |
| `--modo docs`       | "Genera documentación completa en Markdown."                                                                                                                                                                           | Sobrescribe el archivo original. |
| `--modo seguridad`  | "Actúa como un auditor de ciberseguridad (DevSecOps). Analiza el código en busca de vulnerabilidades OWASP (Inyección SQL, XSS, mala gestión de JWT). Devuelve un reporte en Markdown."           | Guarda un archivo `Auditoria_Seguridad.md` en la raíz. |
| `--modo dockerfile` | "Genera un Dockerfile multi-stage optimizado para Spring Boot usando Eclipse Temurin 21. Genera también un docker-compose.yml para orquestar los servicios."                                      | Crea `Dockerfile` y `docker-compose.yml` en la raíz. |
| `--modo chat`       | "Eres un asistente de desarrollo. Responde preguntas sobre el código proporcionado en el contexto."                                                                                               | Imprime en consola (REPL interactivo). |

---

## 6. Ejemplos de Uso Avanzados y Flujo Real

### A. Generación de Tests Unitarios (Flujo Completo)
```bash
python agente_gemini.py --modo tests --clase EvaluacionServiceImpl --microservicio examenes-service
```
**¿Qué ocurre internamente?**
1. Busca `EvaluacionServiceImpl.java` en `examenes-service/src/main/java/...`.
2. Lee la clase y detecta que importa `EvaluacionRepository` y `ExamenRepository`.
3. Busca y lee esos repositorios.
4. Envía a Gemini: *Prompt de Tests* + *Código de EvaluacionServiceImpl* + *Código de los Repositorios*.
5. Gemini devuelve el código del test con los Mocks correctamente configurados.
6. El script extrae el código y lo guarda en `examenes-service/src/test/java/.../EvaluacionServiceImplTest.java`.

### B. Auditoría de Seguridad Global
```bash
python agente_gemini.py --modo seguridad --todo --microservicio usuarios-service
```
**¿Qué ocurre internamente?**
1. El flag `--todo` activa la función `buscar_todos()`.
2. Concatena todos los Controladores, Servicios y configuraciones de Seguridad (`SecurityConfig.java`, `JwtFilter.java`).
3. Envía el macro-contexto a Gemini con el prompt de auditoría OWASP.
4. Guarda el reporte detallado en `usuarios-service/Auditoria_Seguridad.md`.

### C. Modo Chat Interactivo (REPL)
```bash
python agente_gemini.py --modo chat --microservicio api-gateway
```
**¿Qué ocurre internamente?**
1. Carga todo el código del `api-gateway` en memoria.
2. Abre un prompt en la terminal: `Agente IA > `
3. El desarrollador escribe: *"¿Cómo está configurado el CORS globalmente?"*
4. El agente responde basándose en el archivo `application.properties` y `ApiGatewayApplication.java` que tiene en su contexto. Mantiene el historial de la conversación hasta que el usuario escribe `exit`.