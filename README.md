# 🤖 Sistema de Asistencia IA Híbrido (Multi-Agente) — v4.0

Ecosistema de Inteligencia Artificial con arquitectura **100% local y privada**, basado en el patrón **Router → Worker → Supervisor**. Todos los modelos de lenguaje corren en Ollama (Railway o local), eliminando la dependencia de APIs externas para el procesamiento de datos sensibles.

---

## 📁 Estructura del Directorio

```
ia-proyecto/
├── api_chatbot.py          # Servidor principal FastAPI (v4.0 — 100% Ollama)
├── agente_gemini.py        # Herramienta CLI para análisis de código Java
├── agente_creador.py       # Agente autónomo creador de proyectos (LangGraph)
├── index.html              # Interfaz web del chatbot
├── documentos/             # PDFs para el sistema RAG (se vectorizan automáticamente)
├── .env                    # Variables de entorno (no subir a Git)
└── proyectos_generados/    # Carpeta de salida del agente_creador.py
```

---

## 🏗️ Arquitectura del Sistema

### `api_chatbot.py` — El Chatbot (Flujo de una petición)

```
Usuario
  │
  ▼
FastAPI /chat
  │
  ├─► [PASO 1] Qwen2.5:7b (Router)
  │     └── Analiza la intención y elige herramienta + SQL
  │
  ├─► [PASO 2] Herramienta ejecutada en Python
  │     ├── buscar_en_documentos → FAISS (RAG local con nomic-embed-text)
  │     ├── consultar_base_datos → MySQL
  │     └── ver_tablas          → MySQL
  │
  ├─► [PASO 3] Mistral (Worker)
  │     └── Redacta respuesta natural con la evidencia obtenida
  │
  ├─► [PASO 4] Qwen2.5:7b (Supervisor)
  │     └── Valida que la respuesta no tenga JSON ni alucinaciones
  │
  └─► Respuesta final al usuario + guardado en MySQL
```

### `agente_creador.py` — El Creador de Proyectos (LangGraph)

```
Input: descripción en lenguaje natural
  │
  ▼
[Nodo 1] Arquitecto (Gemini / configurable)
  └── Genera plan JSON: lista de archivos con descripción técnica
  │
  ▼
[Nodo 2] Programador (Ollama / configurable)
  └── Para cada archivo: genera código y llama a crear_archivo()
  │
  ▼
Output: archivos creados en ./proyectos_generados/
```

---

## ⚙️ Modelos utilizados

| Rol | Modelo                   | Dónde corre | Para qué |
|-----|--------------------------|-------------|----------|
| **Worker** | `mistral`                | Ollama (Railway) | Redacta respuestas en lenguaje natural |
| **Router / Supervisor** | `qwen2.5:7b`             | Ollama (Railway) | Toma decisiones estructuradas (JSON) |
| **Embeddings RAG** | `nomic-embed-text`       | Ollama (Railway) | Vectoriza los PDFs localmente |
| **Arquitecto** (agente_creador) | `gemini-3.1-pro-preview` | Google API | Diseña la estructura del proyecto |
| **Programador** (agente_creador) | `qwen3.5:4b`             | Ollama | Genera el código archivo por archivo |
| **Análisis código** (agente_gemini) | `gemini-3.1-pro-preview` | Google API | Tests, docs, refactoring, seguridad |

---

## 🔌 Variables de Entorno (`.env`)

Crea un archivo `.env` en el directorio `ia-proyecto/` con:

```env
# Base de datos MySQL
DATABASE_URL=mysql+pymysql://root:12345@localhost:3306/examenes

# Google Gemini (para agente_gemini.py y agente_creador.py)
GOOGLE_API_KEY=tu_api_key_de_google_ai_studio

# Alertas por correo (opcional — para el webhook de GitHub)
GMAIL_USER=tu_correo@gmail.com
GMAIL_PASS=tu_app_password_de_gmail

# Carpeta de PDFs (opcional, por defecto: "documentos")
PDF_DIR=documentos
```

> ⚠️ **Nunca subas `.env` a Git.** Añádelo al `.gitignore`.

---

## 🗃️ Esquema de base de datos requerido

El sistema necesita estas tablas en MySQL además de las tablas del proyecto:

```sql
-- Historial de conversaciones (se crea automáticamente)
-- Tabla: message_store (creada por SQLChatMessageHistory)

-- Memoria a largo plazo del agente (debes crearla manualmente)
CREATE TABLE IF NOT EXISTS conocimiento_validado (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    pregunta            TEXT NOT NULL,
    respuesta           TEXT NOT NULL,
    latencia_segundos   FLOAT,
    tokens_entrada      INT,
    tokens_salida       INT,
    tokens_por_segundo  FLOAT,
    fecha               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 📦 Instalación

```bash
# Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate      # Linux/Mac

# Instalar dependencias
pip install fastapi uvicorn sqlalchemy pymysql python-dotenv \
    langchain langchain-google-genai langchain-ollama \
    langchain-community langchain-anthropic langchain-text-splitters \
    langgraph pydantic faiss-cpu pypdf
```

---

## ▶️ Ejecución

### Chatbot (`api_chatbot.py`)

```bash
uvicorn api_chatbot:app --host 0.0.0.0 --port 8000 --reload
```

Accede en: `http://localhost:8000`

### Agente creador de proyectos (`agente_creador.py`)

```bash
py agente_creador.py
```

Te pedirá una descripción y generará los archivos en `./proyectos_generados/`.

### Agente de análisis de código (`agente_gemini.py`)

```bash
# Generar tests unitarios para una clase
py agente_gemini.py --modo tests --clase EvaluacionServiceImpl --microservicio examenes-service

# Analizar bugs y problemas SOLID
py agente_gemini.py --modo analisis --clase ExamenController --microservicio examenes-service

# Auditoría de seguridad
py agente_gemini.py --modo seguridad --clase SecurityConfig --microservicio examenes-service

# Refactoring automático
py agente_gemini.py --modo refactor --clase ReporteServiceImpl --microservicio examenes-service

# Generar documentación Markdown
py agente_gemini.py --modo docs --todo --microservicio examenes-service

# Generar README.md del proyecto
py agente_gemini.py --modo readme --microservicio examenes-service

# Generar Dockerfile y docker-compose optimizados
py agente_gemini.py --modo dockerfile

# Generar script SQL (migraciones, datos de prueba)
py agente_gemini.py --modo sql --descripcion "Genera datos de prueba para evaluaciones"

# Generar frontend JS/HTML
py agente_gemini.py --modo frontend --descripcion "Formulario para crear exámenes"

# Modo chat libre con contexto del proyecto completo
py agente_gemini.py --modo chat --microservicio examenes-service
```

---

## 🌐 Endpoints de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/` | Sirve la interfaz web (`index.html`) |
| `POST` | `/chat` | Envía un mensaje al agente |
| `GET` | `/historial/{session_id}` | Recupera el historial de una sesión |
| `GET` | `/chats` | Lista todos los IDs de sesión |
| `GET` | `/estado` | Health check: modelos, BD y RAG |
| `POST` | `/recargar-pdfs` | Recarga los PDFs sin reiniciar |
| `POST` | `/github-webhook` | Webhook para auditorías automáticas en cada commit |

### Ejemplo de petición al chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "mi_sesion_1", "mensaje": "¿Cuál es la nota media de los alumnos?"}'
```

### Respuesta

```json
{
  "status": "ok",
  "respuesta": "La nota media de los alumnos es 6.8 sobre 10.",
  "corregida_por_supervisor": false
}
```

---

## 🔔 Webhook de GitHub (Auditoría proactiva)

El endpoint `/github-webhook` escucha eventos `push` de GitHub. Cuando detecta un commit:

1. Identifica los archivos modificados
2. Mistral genera un informe de auditoría de seguridad y buenas prácticas
3. El agente te envía el informe automáticamente por **Gmail**

### Configurar en GitHub

Ve a tu repositorio → `Settings` → `Webhooks` → `Add webhook`:

- **Payload URL:** `https://tu-dominio/github-webhook`
- **Content type:** `application/json`
- **Events:** `Just the push event`

### Configurar Gmail

1. Activa la verificación en dos pasos en tu cuenta Google
2. Ve a `Cuenta de Google` → `Seguridad` → `Contraseñas de aplicación`
3. Genera una contraseña para "Mail" y ponla en `GMAIL_PASS` del `.env`

---

## 📊 Métricas de rendimiento

Cada respuesta registra automáticamente en `conocimiento_validado`:

- **Latencia total** (segundos)
- **Tokens de entrada** (prompt enviado a Mistral)
- **Tokens de salida** (respuesta generada)
- **Velocidad** (tokens/segundo)

Se imprimen en consola con este formato:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ TIEMPO TOTAL: 3.42 s
┃ TOKENS WORKER: In: 512 | Out: 148
┃ VELOCIDAD: 43.3 tokens/segundo
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

---

## 📄 Gestión de PDFs (RAG)

Coloca cualquier PDF en la carpeta `documentos/`. Al arrancar el servidor se vectorizan automáticamente usando `nomic-embed-text` (Ollama). Para recargar sin reiniciar:

```bash
curl -X POST http://localhost:8000/recargar-pdfs
```

---

## ☁️ Despliegue de Ollama en Railway

1. Nuevo proyecto → `Deploy from Docker image` → imagen: `ollama/ollama`
2. **Volumes:** monta `/root/.ollama` para persistir los modelos
3. **Networking:** genera dominio público en puerto `11434`
4. Descarga los modelos desde la consola de Railway:

```bash
ollama pull mistral
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

5. Actualiza `URL_OLLAMA` en `api_chatbot.py` con tu URL de Railway

---

## 🔧 Cambiar modelos

Todo se controla con tres variables en `api_chatbot.py`:

```python
MODELO_WORKER     = "mistral"         # El que redacta
MODELO_SUPERVISOR = "qwen2.5:7b"      # El que decide y valida
MODELO_EMBED      = "nomic-embed-text" # El que vectoriza PDFs
```

Y en `agente_creador.py`:

```python
arquitecto_llm  = obtener_modelo("gemini", "gemini-3.1-pro-preview")
programador_llm = obtener_modelo("local",  "qwen3.5:4b")
```