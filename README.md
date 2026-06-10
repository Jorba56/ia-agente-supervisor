# 🤖 Ecosistema de Inteligencia Artificial — Documentación Conjunta

> **Proyecto conjunto:** Jorge Barriga Rubio · Pablo Pacheco  
> **Última actualización:** Junio 2026

Este documento describe los dos sistemas de IA desarrollados de forma independiente para el proyecto **ExamenApp**, comparando sus enfoques, arquitecturas y decisiones técnicas.

---

## 👥 Resumen comparativo

| | **Jorge** (`ia-proyecto/`)      | **Pablo** (`ms-chatbot/`) |
|---|---------------------------------|---|
| **Nombre** | Sistema Multi-Agente v4.0       | ms-chatbot |
| **Framework** | FastAPI + LangChain + LangGraph | FastAPI + LangChain + LangGraph |
| **LLMs** | Ollama (Railway) — 100% local   | Groq (nube) + Ollama (local, dev) |
| **Router** | Qwen2.5:7b con Pydantic         | Detección por palabras clave |
| **Worker** | Mistral                         | llama-3.1-8b-instant (Groq) |
| **Supervisor** | Qwen2.5:7b (síncrono)           | llama-3.1-8b-instant (asíncrono) |
| **Embeddings RAG** | `nomic-embed-text` (Ollama)     | `nomic-embed-text` (Ollama) |
| **Vector store** | Turbovec                           | Turbovec |
| **BD relacional** | MySQL (`examenes`)              | MySQL (múltiples schemas) |
| **BD de grafos** | ❌ No implementado               | ✅ Neo4j (Knowledge Graph) |
| **OCR** | ❌ No implementado               | ✅ Tesseract |
| **Webhook GitHub** | ✅ Auditoría por email           | ❌ No implementado |
| **Métricas** | Tokens, latencia, vel. (MySQL)  | Telemetría en BD separada |
| **Agente creador** | ✅ `agente_creador.py`           | ❌ No implementado |
| **CLI análisis código** | ✅ `agente_gemini.py`            | ❌ No implementado |
| **Despliegue** | Ollama en Railway               | Docker Compose completo |

---

## 📁 Estructura de directorios

### Jorge — `ia-proyecto/`
```
ia-proyecto/
├── api_chatbot.py          # Servidor principal FastAPI v4.0
├── agente_gemini.py        # CLI para análisis de código Java
├── agente_creador.py       # Agente autónomo creador de proyectos
├── index.html              # Interfaz web del chatbot
├── documentos/             # PDFs vectorizados automáticamente
├── .env                    # Variables de entorno
└── proyectos_generados/    # Salida del agente_creador.py
```

### Pablo — `ms-chatbot/`
```
chatbot/
├── api_chatbot.py          # Servidor principal FastAPI
├── index.html              # Interfaz web del chatbot
├── documentos/             # PDFs y archivos indexados
├── requirements.txt        # Dependencias Python
└── Dockerfile              # Imagen Docker del servicio
```

---

## 🏗️ Arquitectura del sistema

### Jorge — Patrón Router → Worker → Supervisor (100% local)

```
Usuario
  │
  ▼
FastAPI /chat
  │
  ├─► [PASO 1] Qwen2.5:7b (Router — Pydantic structured output)
  │     └── Analiza intención y genera SQL directamente
  │
  ├─► [PASO 2] Herramienta Python (sin pasar por el LLM)
  │     ├── buscar_en_documentos → Turbovec + nomic-embed-text
  │     ├── consultar_base_datos → MySQL
  │     └── ver_tablas           → MySQL
  │
  ├─► [PASO 3] Mistral (Worker — redacta respuesta natural)
  │
  ├─► [PASO 4] Qwen2.5:7b (Supervisor síncrono — valida antes de responder)
  │
  └─► Respuesta + métricas guardadas en MySQL
```

### Pablo — Patrón Enrutador por palabras clave + Supervisor asíncrono

```
Usuario
  │
  ▼
FastAPI /chat
  │
  ├─► Análisis de contexto (archivos mencionados, palabras técnicas)
  │
  ├─► Rutas automáticas:
  │     ├── RAG DOC     → Turbovec + búsqueda semántica
  │     ├── CÓDIGO      → Análisis técnico Spring/Java
  │     └── SQL/GRAFO   → Agente LangChain + Neo4j
  │
  ├─► LLM Principal (Groq llama-3.1-8b / Ollama llama3.2)
  │     └── Respuesta al usuario (SÍNCRONO)
  │
  └─► LLM Supervisor (ASÍNCRONO — en background)
        ├── Evalúa calidad: BUENA o MALA
        ├── Detecta alucinaciones
        └── Guarda en db_chatbot_telemetria
```

**Diferencia clave:** En Jorge el supervisor bloquea la respuesta hasta validarla. En Pablo el supervisor trabaja en background y no ralentiza al usuario, pero la corrección llega tarde.

---

## 🧠 Modelos de IA utilizados

### Jorge

| Rol | Modelo | Dónde corre |
|-----|--------|-------------|
| Router + Supervisor | `qwen2.5:7b` | Ollama (Railway) |
| Worker (redacta) | `mistral` | Ollama (Railway) |
| Embeddings RAG | `nomic-embed-text` | Ollama (Railway) |
| Arquitecto (agente_creador) | `gemini-1.5-flash` | Google API |
| Análisis código (agente_gemini) | `gemini-1.5-flash` | Google API |

### Pablo

| Rol | Modelo producción | Modelo desarrollo |
|-----|-------------------|-------------------|
| Chat principal | `llama-3.1-8b-instant` (Groq) | `llama3.2` (Ollama local) |
| Grafo Neo4j | `llama-3.1-8b-instant` (Groq) | `llama3.2:1b` (Ollama local) |
| Supervisor telemetría | `llama-3.1-8b-instant` (Groq) | `llama3.2` (Ollama local) |
| Embeddings RAG | `nomic-embed-text` | `nomic-embed-text` |

---

## 🗄️ Base de datos y persistencia

### Jorge

**MySQL** — una sola base de datos `examenes`:

```sql
-- Historial de conversaciones (auto-creada por LangChain)
message_store: session_id, message, created_at

-- Memoria a largo plazo + métricas (crear manualmente)
CREATE TABLE conocimiento_validado (
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

**Turbovec** — índice vectorial en memoria ultraveloz, recargable sin reiniciar.

### Pablo

**MySQL** — múltiples schemas:

| Schema | Tablas principales |
|--------|--------------------|
| `db_examenes` | examenes, preguntas, examen_preguntas |
| `db_usuarios` | usuarios, roles, usuario_roles |
| `db_evaluaciones` | evaluaciones, respuestas_alumno |
| `db_chatbot_telemetria` | preguntas_correctas, preguntas_incorrectas |

**Neo4j** — Knowledge Graph con nodos y relaciones:
- **Nodos:** Microservicio, BaseDatos, Endpoint, Entidad, Tecnologia, Clase, Metodo...
- **Relaciones:** LLAMA_A, DEPENDE_DE, GESTIONA, EXPONE, IMPLEMENTA, USA...

**Turbovec** — igual que Jorge.

---

## 🌐 Endpoints de la API

### Comunes a ambos

| Método | Endpoint | Jorge | Pablo |
|--------|----------|-------|-------|
| `GET` | `/` | ✅ Sirve `index.html` | ✅ Sirve `index.html` |
| `POST` | `/chat` | ✅ | ✅ |
| `GET` | `/historial/{id}` | ✅ | ❌ (historial en body) |
| `GET` | `/chats` | ✅ Lista sesiones | ❌ |
| `GET` | `/estado` | ✅ Health check | ❌ |
| `POST` | `/recargar-pdfs` | ✅ | ❌ |

### Exclusivos de Jorge

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/github-webhook` | Auditoría automática en cada commit + email |

### Exclusivos de Pablo

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/indexar-grafo` | Reconstruye el Knowledge Graph Neo4j |
| `DELETE` | `/limpiar-grafo` | Elimina todos los nodos y relaciones |
| `POST` | `/re-evaluar-todo` | Re-evalúa todos los registros históricos |
| `POST` | `/re-evaluar/{id}` | Re-evalúa un registro individual |

### Formato del endpoint `/chat`

**Jorge:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "mi_sesion_1", "mensaje": "¿Cuál es la nota media?"}'
```
```json
{
  "status": "ok",
  "respuesta": "La nota media es 6.8 sobre 10.",
  "corregida_por_supervisor": false
}
```

**Pablo:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"mensaje": "¿Cuántos usuarios hay?", "chat_id": "usuario_123", "historial": []}'
```
```json
{
  "status": "ok",
  "respuesta": "Hay 15 usuarios registrados.",
  "fuente_rag": null,
  "ruta_usada": "Agente SQL/Grafo",
  "tiempo_segundos": 0.87
}
```

---

## 🔌 Variables de entorno

### Jorge — `.env`

```env
DATABASE_URL=mysql+pymysql://root:12345@localhost:3306/examenes
GOOGLE_API_KEY=tu_api_key_de_google_ai_studio
GMAIL_USER=tu_correo@gmail.com         # Para el webhook de GitHub
GMAIL_PASS=tu_app_password_de_gmail    # Contraseña de aplicación Gmail
PDF_DIR=documentos                      # Opcional, por defecto "documentos"
```

### Pablo — variables de entorno

```env
# Base de datos
DATABASE_URL=mysql+pymysql://root:root@db-mysql:3306/db_examenes
TELEMETRY_DATABASE_URL=mysql+pymysql://root:root@db-mysql:3306/mysql

# Knowledge Graph
NEO4J_URI=bolt://db-neo4j:7687

# Motor IA — Groq (producción)
PROVEEDOR_LLM=groq
GROQ_API_KEY_CHAT=gsk_...
GROQ_API_KEY_SUPERVISOR=gsk_...        # API key separada para el supervisor
MODELO_GROQ=llama-3.1-8b-instant
MODELO_GROQ_SUPERVISOR=llama-3.1-8b-instant

# Motor IA — Ollama (desarrollo)
OLLAMA_HOST=http://ollama3:11434
OLLAMA_SUPERVISOR_HOST=http://ollama-supervisor:11434
MODELO_LLM=llama3.2
MODELO_GRAFO=llama3.2:1b
```

---

## 📦 Instalación y dependencias

### Jorge

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate     # Linux/Mac

pip install fastapi uvicorn sqlalchemy pymysql python-dotenv \
    langchain langchain-google-genai langchain-ollama \
    langchain-community langchain-anthropic langchain-text-splitters \
    langgraph pydantic turbovec pypdf requests
```

### Pablo — `requirements.txt`

```txt
fastapi uvicorn pydantic python-dotenv pymysql SQLAlchemy
pytesseract pdf2image python-docx pypdf
langchain langchain-openai langchain-community langchain-experimental
langgraph langchain-text-splitters langchain-ollama
langchain-neo4j langchain-groq
faiss-cpu==1.9.0 neo4j
```

> **Diferencia notable:** Pablo necesita `tesseract-ocr` instalado en el sistema para OCR de PDFs. Jorge usa `PyPDFDirectoryLoader` sin OCR.

---

## ▶️ Ejecución

### Jorge

```bash
# Chatbot principal
uvicorn api_chatbot:app --host 0.0.0.0 --port 8000 --reload

# Agente creador de proyectos
py agente_creador.py

# Herramienta CLI de análisis de código Java
py agente_gemini.py --modo tests --clase EvaluacionServiceImpl --microservicio examenes-service
py agente_gemini.py --modo analisis --clase ExamenController --microservicio examenes-service
py agente_gemini.py --modo seguridad --clase SecurityConfig --microservicio examenes-service
py agente_gemini.py --modo refactor --clase ReporteServiceImpl --microservicio examenes-service
py agente_gemini.py --modo docs --todo --microservicio examenes-service
py agente_gemini.py --modo readme --microservicio examenes-service
py agente_gemini.py --modo dockerfile
py agente_gemini.py --modo sql --descripcion "Genera datos de prueba"
py agente_gemini.py --modo frontend --descripcion "Formulario para crear exámenes"
py agente_gemini.py --modo chat --microservicio examenes-service
```

### Pablo

```bash
# Docker Compose (recomendado — levanta todo)
git clone https://github.com/Ppacheco306/generador-examenes-back.git
cd generador-examenes-back
docker-compose up -d

# Verificar
curl http://localhost:8000/

# Construir el Knowledge Graph (opcional, tarda 5-10 min)
curl -X POST http://localhost:8000/indexar-grafo

# Desarrollo local
pip install -r chatbot/requirements.txt
cd chatbot
uvicorn api_chatbot:app --reload --host 0.0.0.0 --port 8000
```

---

## 🐳 Despliegue

### Jorge — Ollama en Railway

1. Railway → `Deploy from Docker image` → `ollama/ollama`
2. **Volumes:** monta `/root/.ollama` para persistir modelos
3. **Networking:** genera dominio público en puerto `11434`
4. Descarga los modelos desde la consola:

```bash
ollama pull mistral
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

5. Actualiza `URL_OLLAMA` en `api_chatbot.py`

### Pablo — Docker Compose completo

```yaml
ms-chatbot:
  build:
    context: ./chatbot
    dockerfile: Dockerfile
  container_name: chatbot-fastapi
  ports:
    - "8000:8000"
  environment:
    - DATABASE_URL=mysql+pymysql://root:root@db-mysql:3306/db_examenes
    - NEO4J_URI=bolt://db-neo4j:7687
    - OLLAMA_HOST=http://ollama3:11434
    - MODELO_LLM=llama3.2
  depends_on:
    db-mysql:
      condition: service_healthy
    db-neo4j:
      condition: service_started
    ollama-init:
      condition: service_completed_successfully
```

**Dockerfile de Pablo** (incluye OCR):
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    tesseract-ocr tesseract-ocr-spa poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "api_chatbot:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 📊 Métricas y telemetría

### Jorge — cuadro de mandos en consola + MySQL

Cada petición registra en `conocimiento_validado`:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ TIEMPO TOTAL: 3.42 s
┃ TOKENS WORKER: In: 512 | Out: 148
┃ VELOCIDAD: 43.3 tokens/segundo
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### Pablo — telemetría asíncrona en `db_chatbot_telemetria`

El supervisor evalúa cada respuesta en background y la clasifica:

- **`preguntas_correctas`** — respuestas validadas como buenas
- **`preguntas_incorrectas`** — alucinaciones detectadas con análisis crítico y respuesta mejorada

Criterios de evaluación: datos reales vs inventados, tablas existentes, excepciones SQL expuestas.

---

## 🔔 Funcionalidades exclusivas

### Jorge — Webhook de GitHub

El endpoint `/github-webhook` escucha eventos `push`. Al detectar un commit:
1. Identifica archivos modificados
2. Mistral genera un informe de auditoría de seguridad
3. El agente envía el informe por **Gmail** automáticamente

```bash
# Configurar en GitHub: Settings → Webhooks → Add webhook
# Payload URL: https://tu-dominio/github-webhook
# Content type: application/json
# Events: Just the push event
```

Para Gmail: activa verificación en 2 pasos → `Contraseñas de aplicación` → añade a `.env`.

### Pablo — Knowledge Graph (Neo4j)

Transforma automáticamente los documentos del proyecto en un grafo de conocimiento:

```bash
# Reconstruir el grafo desde cero (5-10 minutos)
curl -X POST http://localhost:8000/indexar-grafo

# Limpiar el grafo
curl -X DELETE http://localhost:8000/limpiar-grafo
```

### Jorge — Agente creador de proyectos

Genera proyectos completos desde una descripción en lenguaje natural usando LangGraph:

```
py agente_creador.py
¿Qué sistema quieres construir?: Una API REST en Spring Boot para gestionar tareas
→ Crea automáticamente todos los archivos en ./proyectos_generados/
```

### Jorge — CLI de análisis de código

Analiza, documenta y genera código para proyectos Java directamente desde terminal con acceso al código fuente completo.

---

## 🔍 Health checks

### Jorge

```bash
curl http://localhost:8000/estado
```
```json
{
  "status": "ok",
  "worker": "mistral",
  "supervisor": "qwen2.5:7b",
  "bd_conectada": true,
  "rag_activo": true
}
```

### Pablo

```bash
# API
curl http://localhost:8000/

# MySQL
mysql -h localhost -u root -proot -e "SELECT VERSION();"

# Neo4j
curl -u neo4j:rootpassword http://localhost:7474/

# Ollama
curl http://localhost:11434/api/tags
```

---

## 🛠️ Troubleshooting

| Problema | Sistema | Solución |
|----------|---------|----------|
| `incomplete chunked read` | Jorge | Modelo no existe en Ollama. Verifica con `/api/tags` |
| `GROQ_API_KEY no definida` | Pablo | `export GROQ_API_KEY_CHAT="gsk_..."` |
| `Neo4j no conectado` | Pablo | `docker ps \| grep neo4j` |
| `OCR fallando en PDF` | Pablo | `apt-get install tesseract-ocr tesseract-ocr-spa` |
| `embedding-001 not found` | Jorge | Usar `models/gemini-embedding-001` sin `models/` prefix |
| `Respuestas lentas > 5s` | Pablo | Cambiar a Groq en lugar de Ollama local |
| `[object Object]` en chat | Jorge | Extraer `.content` del AIMessage correctamente |

---

## 📋 Cambiar modelos

### Jorge — `api_chatbot.py`

```python
MODELO_WORKER     = "mistral"          # Cambia aquí el que redacta
MODELO_SUPERVISOR = "qwen2.5:7b"       # Cambia aquí el que valida
MODELO_EMBED      = "nomic-embed-text" # Cambia aquí el de embeddings
```

### Pablo — variables de entorno

```env
MODELO_GROQ=llama-3.1-8b-instant       # Producción
MODELO_LLM=llama3.2                    # Desarrollo local
MODELO_GRAFO=llama3.2:1b               # Para Neo4j (ligero)
```

---

## 👨‍💻 Autores

| Desarrollador | GitHub | Proyecto |
|---------------|--------|---------|
| **Jorge Barriga Rubio** | — | `ia-proyecto/` — Sistema Multi-Agente v4.0 |
| **Pablo Pacheco** | [@Ppacheco306](https://github.com/Ppacheco306) | `ms-chatbot/` — Microservicio IA con Neo4j |