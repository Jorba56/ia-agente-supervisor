# 🤖 ms-chatbot - Microservicio de Inteligencia Artificial

## 📋 Índice

1. Introducción

2. Características Principales

3. Arquitectura Técnica

4. Tecnologías Utilizadas

5. Configuración

6. Endpoints

7. Flujo de Conversación

8. Motor de IA

9. Base de Datos y Persistencia

10. Deployment

---

## Introducción

**ms-chatbot** es un microservicio de inteligencia artificial de última generación diseñado para proporcionar un asistente conversacional inteligente dentro del ecosistema ExamenApp. Combina técnicas avanzadas de **Procesamiento de Lenguaje Natural (NLP)**, **Recuperación Aumentada por Generación (RAG)**, **Grafos de Conocimiento** y **OCR** para ofrecer respuestas contextuales y precisas.

El servicio actúa como intermediario entre usuarios y sistemas complejos, permitiendo consultas en lenguaje natural que se traducen automáticamente en acciones sobre bases de datos relacionales y grafos de conocimiento.
 
---

## Características Principales

### 🎯 Capas de Inteligencia Multi-Nivel

#### 1. Asistente de Conversación (Chat Interactivo)

- Responde preguntas generales con soporte multiidioma

- Integración con LLMs de alto rendimiento (Groq o Ollama local)

- Historial de conversación persistente con ID de sesión

- Timeout configurado para optimizar latencia

#### 2. Motor RAG (Recuperación Aumentada por Generación)

- Indexación automática de documentos en múltiples formatos

- PDF: Procesamiento mediante OCR (Tesseract)

- DOCX: Extracción de contenido textual

- Markdown, TXT, Java: Lectura de archivos de código

- Caché vectorial FAISS para búsquedas semánticas rápidas

- Fragmentación de documentos con overlap para contexto continuo

- Respuestas fundamentadas en documentación interna

#### 3. Agente SQL/Grafo Inteligente

- Enrutamiento automático de consultas SQL SELECT

- Acceso estructurado a esquemas de bases de datos

- Validación de seguridad: solo lecturas permitidas

- Soporte para consultas complejas multi-tabla con prefijo db_schema.table

- Integración con Neo4j para relaciones avanzadas

#### 4. Asistente de Código Especializado

- Detección automática de preguntas técnicas

- Soporte para Spring Boot, Java y arquitecturas de microservicios

- Análisis de estructura de proyectos y patrones de código

#### 5. Evaluador Automático (Background AI)

- Supervisión en tiempo real de respuestas generadas

- Clasificación binaria: respuestas buenas vs malas

- Detección de alucinaciones del LLM

- Telemetría persistente para mejora continua

- Re-evaluación masiva de registros históricos

#### 6. Knowledge Graph (Neo4j)

- Transformación automática de documentos en grafos de conocimiento

- Extracción de entidades y relaciones con LLMs especializados

- Relaciones específicas del dominio

- Búsqueda por entidades clave con contexto relacional

---

## Arquitectura Técnica

```

Cliente Web (index.html)

        ↓

FastAPI Uvicorn (Puerto 8000)

├─ Enrutador de Consultas

│  ├─ RAG (Documentos)

│  ├─ Código (Spring/Java)

│  └─ SQL/Grafo (Agente)

        ↓

LLM Triple:

├─ LLM Chat (Respuesta en tiempo real)

├─ LLM Supervisor (Telemetría en background)

└─ LLM Grafo (Neo4j en background)

        ↓

Proveedores IA:

├─ GROQ (Nube - Producción)

└─ OLLAMA (Local - Desarrollo)

        ↓

Persistencia:

├─ MySQL (Relacional)

├─ Neo4j (Grafo - Knowledge Graph)

└─ FAISS (Vectores - Caché de embeddings)

```
 
---

## Tecnologías Utilizadas

### 🔧 Backend

| Tecnología | Versión | Propósito |

|---|---|---|

| Python | 3.11+ | Lenguaje principal |

| FastAPI | Latest | Framework web asincrónico |

| Uvicorn | Latest | Servidor ASGI |

| Pydantic | Latest | Validación de modelos |

### 🧠 Inteligencia Artificial

| Componente | Proveedor | Uso |

|---|---|---|

| ChatGroq | Groq API | LLM chat en tiempo real (producción) |

| ChatOpenAI | OLLAMA Local | LLM alternativo local (desarrollo) |

| LLMGraphTransformer | LangChain | Extracción de entidades a Neo4j |

| OllamaEmbeddings | Ollama | Generación de embeddings (nomic-embed-text) |

| FAISS | Meta | Vector store para búsquedas semánticas |

### 📚 Procesamiento de Documentos

| Librería | Versión | Función |

|---|---|---|

| pytesseract | Latest | OCR para PDFs |

| pdf2image | Latest | Conversión PDF a imágenes |

| python-docx | Latest | Lectura de archivos DOCX |

| LangChain Text Splitters | Latest | Fragmentación inteligente |

### 💾 Persistencia de Datos

| Base de Datos | Versión | Esquemas |

|---|---|---|

| MySQL | 8.3.0 | db_examenes, db_usuarios, db_evaluaciones, db_incidencias, db_chatbot_telemetria |

| Neo4j | 5.18.0 | Knowledge Graph con nodos y relaciones |

### 🔗 ORM y Consultas

| Librería | Uso |

|---|---|

| SQLAlchemy | Abstracción de bases de datos |

| SQLDatabase (LangChain) | Interfaz para consultas SQL seguras |
 
---

## Configuración

### 🌍 Variables de Entorno

**Base de Datos Relacional:**

- `DATABASE_URL`: mysql+pymysql://root:root@db-mysql:3306/db_examenes

- `TELEMETRY_DATABASE_URL`: mysql+pymysql://root:root@db-mysql:3306/mysql

**Knowledge Graph:**

- `NEO4J_URI`: bolt://db-neo4j:7687

**Motor IA - GROQ (Recomendado para Producción):**

- `PROVEEDOR_LLM`: groq

- `GROQ_API_KEY_CHAT`: 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

- `GROQ_API_KEY_SUPERVISOR`: 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

**Motor IA - OLLAMA (Alternativa Local):**

- `OLLAMA_HOST`: http://ollama3:11434

- `OLLAMA_SUPERVISOR_HOST`: http://ollama-supervisor:11434

- `MODELO_LLM`: llama3.2

- `MODELO_GRAFO`: llama3.2:1b

**Modelos:**

- `MODELO_GROQ`: llama-3.1-8b-instant

- `MODELO_GROQ_SUPERVISOR`: llama-3.1-8b-instant

### 🐳 Docker Compose

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

    - OLLAMA_SUPERVISOR_HOST=http://ollama-supervisor:11434

    - MODELO_LLM=llama3.2

    - MODELO_GRAFO=llama3.2:1b

  depends_on:

    db-mysql:

      condition: service_healthy

    db-neo4j:

      condition: service_started

    ollama-init:

      condition: service_completed_successfully

```

### 📄 Dockerfile

```dockerfile

FROM public.ecr.aws/docker/library/python:3.11-slim
 
WORKDIR /app
 
RUN apt-get update && apt-get install -y \

    tesseract-ocr \

    tesseract-ocr-spa \

    poppler-utils \
&& rm -rf /var/lib/apt/lists/*
 
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
 
COPY . .
 
CMD ["uvicorn", "api_chatbot:app", "--host", "0.0.0.0", "--port", "8000"]

```

### ⚙️ Archivo de Requerimientos

```txt

fastapi

uvicorn

pydantic

python-dotenv

pymysql

SQLAlchemy

pytesseract

pdf2image

python-docx

pypdf

langchain

langchain-openai

langchain-community

langchain-experimental

langgraph

langchain-text-splitters

langchain-ollama

langchain-neo4j

langchain-groq

faiss-cpu==1.9.0

neo4j

```
 
---

## Endpoints

### 📍 Endpoints Principales

#### 1. GET / - Interfaz Web

Retorna la interfaz HTML del chatbot.

```bash

GET http://localhost:8000/

```

Response: HTML del interfaz de usuario.
 
---

#### 2. POST /chat - Chat Principal

Realiza una consulta al chatbot con enrutamiento inteligente.

```bash

curl -X POST http://localhost:8000/chat \

  -H "Content-Type: application/json" \

  -d '{

    "mensaje": "¿Cuáles son las tablas de la base de datos?",

    "chat_id": "usuario_123",

    "historial": []

  }'

```

**Parámetros:**

- `mensaje` (string, requerido): Pregunta del usuario

- `chat_id` (string, default: anonimo): ID único de la sesión

- `historial` (array, default: []): Conversación previa

**Response:**

```json

{

  "status": "ok",

  "respuesta": "Las bases de datos disponibles son db_usuarios, db_examenes...",

  "fuente_rag": ["archivo.pdf"],

  "ruta_usada": "Agente SQL/Grafo",

  "tiempo_segundos": 2.45

}

```

**Rutas Automáticas:**

- RAG: Si se mencionan documentos

- Código: Si contiene palabras técnicas (java, spring, controller)

- SQL/Grafo: Consultas a bases de datos

---

#### 3. POST /indexar-grafo

Limpia y reconstruye el grafo de conocimiento desde cero.

```bash

curl -X POST http://localhost:8000/indexar-grafo

```

Response:

```json

{

  "status": "ok",

  "message": "Indexación en grafo iniciada."

}

```

Nota: Operación en background. Duración: 5-10 minutos.
 
---

#### 4. DELETE /limpiar-grafo

Elimina todos los nodos y relaciones del grafo Neo4j.

```bash

curl -X DELETE http://localhost:8000/limpiar-grafo

```

Response:

```json

{

  "status": "ok",

  "message": "Todos los nodos y relaciones eliminados."

}

```
 
---

#### 5. POST /re-evaluar-todo

Inicia re-evaluación masiva de todas las respuestas históricas.

```bash

curl -X POST http://localhost:8000/re-evaluar-todo

```

Response:

```json

{

  "status": "ok",

  "message": "Proceso masivo iniciado."

}

```
 
---

#### 6. POST /re-evaluar/{registro_id}

Re-evalúa un registro individual de la telemetría.

```bash

curl -X POST http://localhost:8000/re-evaluar/42

```

Response:

```json

{

  "status": "ok",

  "message": "Proceso iniciado para ID 42."

}

```
 
---

## Flujo de Conversación

### 🔄 Vida de una Pregunta

1. **RECEPCIÓN DE PREGUNTA**

    - Usuario envía mensaje vía POST /chat

    - Se captura chat_id y historial previo

2. **ANÁLISIS DE CONTEXTO**

    - Buscar archivos mencionados en índice RAG

    - Obtener Few-Shot (respuestas previas aprobadas)

    - Detectar tipo de pregunta

3. **RUTAS AUTOMÁTICAS**

    - RAG DOC: Búsqueda vectorial en documentos

    - CÓDIGO: Análisis técnico

    - SQL/GRAFO: Agente routing inteligente

4. **GENERACIÓN DE RESPUESTA**

    - LLM invocado (Groq/Ollama)

    - Temperatura: 0 (determinista)

    - Max tokens: 800 (chat) o 1024 (grafo)

5. **RETORNO AL USUARIO (SYNC)**

    - Respuesta

    - Fuente RAG (si aplica)

    - Ruta usada

    - Tiempo total

6. **EVALUACIÓN EN BACKGROUND (ASYNC)**

    - LLM Supervisor evalúa calidad

    - Detecta alucinaciones

    - Clasifica: BUENA o MALA

    - Persiste en db_chatbot_telemetria

### 🎯 Matriz de Decisión de Rutas

| Condición | Ruta | Descripción |

|---|---|---|

| Archivos mencionados | RAG | Búsqueda vectorial + Few-Shot |

| Palabras técnicas | Código | Análisis de arquitectura |

| Consultas generales | SQL/Grafo | Agente con herramientas |
 
---

## Motor de IA

### 🧠 Estrategia Multi-Modelo

**LLM Principal (Chat):**

*Producción:*

- Proveedor: ChatGroq

- Modelo: llama-3.1-8b-instant

- Latencia: ~500ms

- Costo: Variable por token

- Fiabilidad: Enterprise-grade

*Desarrollo:*

- Proveedor: ChatOpenAI sobre Ollama

- Modelo: llama3.2

- Latencia: 1-2s

- Costo: Cero

- Fiabilidad: Local

**LLM Grafo (Neo4j):**

- Producción: ChatGroq llama-3.1-8b-instant

- Desarrollo: ChatOpenAI Ollama llama3.2:1b (ligero)

**LLM Supervisor (Telemetría):**

- Clave de API independiente (cuota separada)

- Modelo: llama-3.1-8b-instant

- Ejecuta en background sin afectar chat

- Prompt: Detección de alucinaciones

### 📊 Sistema de Evaluación

#### Criterios de Calificación

**Calificación BUENA si:**

- Respuesta contesta correctamente

- Datos coinciden con base de datos relacional

- No inventa tablas inexistentes

- No inventa nombres de archivos

- Sin excepciones crudas SQL

**Calificación MALA si:**

- Alucinación (inventa datos)

- Tabla/columna inexistente

- Archivo no existe en repositorio

- Excepción de BD sin procesar

#### Almacenamiento en db_chatbot_telemetria

**Tabla: preguntas_correctas**

```sql

id INT AUTO_INCREMENT PRIMARY KEY

chat_id VARCHAR(50)

pregunta TEXT

respuesta TEXT

fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP

```

**Tabla: preguntas_incorrectas**

```sql

id INT AUTO_INCREMENT PRIMARY KEY

chat_id VARCHAR(50)

pregunta TEXT

respuesta_original TEXT

analisis_critica TEXT

respuesta_mejorada TEXT

fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP

```
 
---

## Base de Datos y Persistencia

### 📍 MySQL - Esquemas Estructurados

**db_examenes:**

```

examenes: id, titulo, descripcion, fecha_creacion

preguntas: id, contenido, tipo, dificultad

examen_preguntas: examen_id, pregunta_id

```

**db_usuarios:**

```

usuarios: id, nombre, email, activo

roles: id, nombre

usuario_roles: usuario_id, rol_id

```

**db_evaluaciones:**

```

evaluaciones: id, usuario_id, examen_id, puntuacion, fecha

respuestas_alumno: id, evaluacion_id, pregunta_id, respuesta

```

**db_chatbot_telemetria:**

```

preguntas_correctas: id, chat_id, pregunta, respuesta, fecha

preguntas_incorrectas: id, chat_id, pregunta, respuesta_original, analisis_critica, respuesta_mejorada, fecha

```

### 🕸️ Neo4j - Grafo de Conocimiento

**Nodos Permitidos:**

- Microservicio, BaseDatos, Endpoint, Entidad, Tecnologia

- Libreria, Clase, Metodo, Funcionalidad, Modulo

- Configuracion, Rol

**Relaciones Permitidas:**

- LLAMA_A, DEPENDE_DE, GESTIONA, EXPONE, IMPLEMENTA

- EXTIENDE, USA, CONTIENE, PERSISTE_EN, AUTENTICA_CON, CONECTA_A

---

## Deployment

### 🚀 Docker Compose (Recomendado)

```bash

# Paso 1: Clona el repositorio

git clone https://github.com/Ppacheco306/generador-examenes-back.git

cd generador-examenes-back
 
# Paso 2: Inicia todos los servicios

docker-compose up -d
 
# Paso 3: Verifica que el chatbot está corriendo

curl http://localhost:8000/
 
# Paso 4: Construye el Knowledge Graph (opcional)

curl -X POST http://localhost:8000/indexar-grafo

```

### 🖥️ Ejecución Local (Desarrollo)

```bash

# Paso 1: Instala dependencias Python 3.11+

pip install -r chatbot/requirements.txt
 
# Paso 2: Configura variables de entorno

export DATABASE_URL="mysql+pymysql://root:root@localhost:3310/db_examenes"

export NEO4J_URI="bolt://localhost:7687"

export PROVEEDOR_LLM="groq"

export GROQ_API_KEY_CHAT="gsk_..."

export GROQ_API_KEY_SUPERVISOR="gsk_..."
 
# Paso 3: Inicia el servidor

cd chatbot

uvicorn api_chatbot:app --reload --host 0.0.0.0 --port 8000

```

### ⚙️ Variables Críticas

Antes de desplegar, asegúrate de:

1. ✅ GROQ_API_KEY_CHAT configurada (clave de Groq válida)

2. ✅ GROQ_API_KEY_SUPERVISOR configurada (cuota separada)

3. ✅ DATABASE_URL apunta a MySQL activo

4. ✅ NEO4J_URI accesible (puerto 7687)

5. ✅ Tesseract OCR instalado en el contenedor

6. ✅ Modelos Ollama pre-descargados (llama3.2, nomic-embed-text)

### 🔍 Health Checks

```bash

# Verifica API principal

curl http://localhost:8000/
 
# Verifica MySQL

mysql -h localhost -u root -proot -e "SELECT VERSION();"
 
# Verifica Neo4j

curl -u neo4j:rootpassword http://localhost:7474/
 
# Verifica Ollama

curl http://localhost:11434/api/tags

```

### 📊 Monitoreo

**Logs del contenedor:**

```bash

docker logs -f chatbot-fastapi

```

**Rendimiento en tiempo real:**

- Chat: 500ms-2s por respuesta

- OCR/Indexación: 10-30s por documento

- Grafo: 5-10 minutos por reconstrucción

---

## Ejemplos de Uso

### Caso 1: Consulta de Documentos (RAG)

```bash

curl -X POST http://localhost:8000/chat \

  -H "Content-Type: application/json" \

  -d '{

    "mensaje": "¿Qué dice el archivo README sobre las tecnologías?",

    "chat_id": "usuario_doc_001"

  }'

```

Response:

```json

{

  "status": "ok",

  "respuesta": "El README menciona que se utiliza Java 21, Spring Boot 4.0.3...",

  "fuente_rag": ["README.md"],

  "ruta_usada": "RAG de Documentos (Caché)",

  "tiempo_segundos": 1.23

}

```

### Caso 2: Consulta SQL

```bash

curl -X POST http://localhost:8000/chat \

  -H "Content-Type: application/json" \

  -d '{

    "mensaje": "¿Cuántos usuarios están registrados en el sistema?",

    "chat_id": "usuario_sql_001"

  }'

```

Response:

```json

{

  "status": "ok",

  "respuesta": "Según la base de datos, hay 15 usuarios registrados.",

  "fuente_rag": null,

  "ruta_usada": "Agente SQL/Grafo",

  "tiempo_segundos": 0.87

}

```

### Caso 3: Pregunta Técnica

```bash

curl -X POST http://localhost:8000/chat \

  -H "Content-Type: application/json" \

  -d '{

    "mensaje": "¿Cómo implementaría un filtro en Spring Boot?",

    "chat_id": "usuario_code_001"

  }'

```

Response:

```json

{

  "status": "ok",

  "respuesta": "Para implementar un filtro en Spring Boot, puedes crear una clase que implemente OncePerRequestFilter...",

  "fuente_rag": null,

  "ruta_usada": "Asistente de Código",

  "tiempo_segundos": 1.45

}

```
 
---

## Troubleshooting

### Error: GROQ_API_KEY_CHAT no definida

**Solución:** Asegúrate de configurar la variable de entorno:

```bash

export GROQ_API_KEY_CHAT="gsk_JtFBTq3EGxJjeFs..."

```

### Error: Neo4j no está conectado

**Solución:** Verifica que Neo4j está corriendo:

```bash

docker ps | grep neo4j

curl -u neo4j:rootpassword http://localhost:7474/

```

### Error: OCR fallando en PDF

**Solución:** Instala Tesseract:

```bash

# Linux

apt-get install tesseract-ocr tesseract-ocr-spa
 
# macOS

brew install tesseract
 
# Windows

# Descarga del instalador oficial

```

### Error: Respuestas lentas (más de 5 segundos)

**Solución:**

- Aumenta límites de RAM para Ollama en docker-compose.yml

- Usa Groq en lugar de Ollama local

- Reduce tamaño del caché FAISS

---

## Contribución y Mejoras

Para contribuir al desarrollo de ms-chatbot:

1. Crea una rama: `git checkout -b feature/nueva-funcionalidad`

2. Haz commits descriptivos: `git commit -m "Agregar descripción"`

3. Push a la rama: `git push origin feature/nueva-funcionalidad`

4. Abre un Pull Request

---

## Licencia

Este proyecto es parte de ExamenApp y sigue la misma licencia del repositorio principal.
 
---

## Contacto

Para preguntas o sugerencias sobre ms-chatbot, contacta con el equipo de desarrollo.

**Última actualización:** 2026-06-10
 