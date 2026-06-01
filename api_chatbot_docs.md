# Documentación Técnica: `api_chatbot.py`

## 1. Visión General y Filosofía de Arquitectura
El archivo `api_chatbot.py` define un **Microservicio de Inteligencia Artificial** construido sobre **FastAPI**. Implementa un Agente Conversacional avanzado utilizando el framework **LangChain** y **LangGraph**.

La filosofía principal de este módulo es la **Arquitectura de Modelos Duales (Patrón Supervisor)**:
1.  **Modelo Redactor (Ollama / Mistral):** Se encarga de la generación de lenguaje natural. Al ser un modelo local/privado, reduce los costes de inferencia y mantiene un tono conversacional fluido.
2.  **Modelo Enrutador y Supervisor (Google Gemini):** Se utiliza por su alta capacidad de razonamiento lógico. Actúa en dos fases críticas:
    *   *Router:* Decide qué herramienta usar basándose en la pregunta del usuario.
    *   *Validador:* Revisa la respuesta generada por Mistral antes de enviarla al usuario, asegurando que no haya alucinaciones, exposición de código SQL/JSON, ni invención de datos.

---

## 2. Flujo de Ejecución Interno (Pipeline del Agente)
Cuando un usuario envía un mensaje al endpoint `/chat`, el sistema ejecuta un pipeline estricto:

1.  **Recuperación de Contexto:** Se extrae el historial de la conversación (`session_id`) desde MySQL usando `SQLChatMessageHistory`.
2.  **Búsqueda de Ejemplos (Few-Shot):** Se busca en la tabla `conocimiento_validado` si existen preguntas similares respondidas en el pasado para guiar al modelo.
3.  **Enrutamiento (Gemini):** El modelo evalúa la pregunta y devuelve un JSON estricto decidiendo qué herramienta ejecutar (`buscar_en_documentos`, `consultar_base_datos`, `ver_tablas` o `ninguna`).
4.  **Ejecución de Herramienta:** Se ejecuta la función Python correspondiente. Se aplican capas de "blindaje" para limpiar los parámetros enviados por el LLM.
5.  **Redacción (Mistral):** Se le proporciona a Mistral el historial, los ejemplos, la pregunta y el resultado crudo de la herramienta. Mistral redacta un borrador en lenguaje natural.
6.  **Supervisión (Gemini):** Gemini evalúa el borrador de Mistral. Si detecta fallos (ej. expone un JSON o inventa un dato), reescribe la respuesta.
7.  **Persistencia y Retorno:** Se guarda la interacción en la memoria SQL y se devuelve la respuesta final al cliente.

---

## 3. Configuración y Variables de Entorno
El microservicio es altamente configurable mediante variables de entorno. Si no se proveen, utiliza valores por defecto orientados a un entorno de desarrollo local.

| Variable | Valor por Defecto | Descripción |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | `AIzaSyBCu...` | Clave de API para acceder a los modelos de Gemini (LLM y Embeddings). |
| `DATABASE_URL` | `mysql+pymysql://root:12345@localhost:3306/examenes` | Cadena de conexión SQLAlchemy a la base de datos principal. |
| `PDF_DIR` | `documentos` | Ruta del directorio local donde se depositan los manuales/PDFs para el RAG. |

**Constantes Internas Modificables:**
*   `MODELO_LLM`: `gemini-3.1-pro-preview` (Usado para supervisión y enrutamiento).
*   `MODELO_EMBED`: `models/gemini-embedding-2` (Usado para vectorizar los PDFs).
*   `TEMPERATURA`: `0.7` (Nivel de creatividad general, aunque el supervisor opera a `0.0` para máxima precisión).

---

## 4. Diagrama de Arquitectura y Componentes

```text
                                ┌─────────────────────────┐
                                │  API Gateway / Cliente  │
                                └────────────┬────────────┘
                                             │ HTTP / REST (JSON)
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FastAPI App (api_chatbot.py)                          │
│                                                                                 │
│  ┌──────────────────────┐      ┌─────────────────────────────────────────────┐  │
│  │   Endpoints (REST)   │◄────►│        LangChain / LangGraph (Agente)       │  │
│  └──────────────────────┘      └─┬───────────────────┬─────────────────────┬─┘  │
│                                  │                   │                     │    │
└──────────────────────────────────┼───────────────────┼─────────────────────┼────┘
                                   │                   │                     │
                      ┌────────────▼─────┐   ┌─────────▼─────────┐  ┌────────▼────────┐
                      │  Ollama (Mistral)│   │   Google Gemini   │  │ FAISS Vector DB │
                      │  (Redactor IA)   │   │(Router/Supervisor)│  │ (RAG Docs PDF)  │
                      │  Temp: 0.0       │   │ Temp: 0.0         │  │ Chunk: 1000/200 │
                      └──────────────────┘   └───────────────────┘  └─────────────────┘
                                   │                   │                     ▲
                                   │                   │                     │
                                   ▼                   ▼                     │
                      ┌──────────────────────────────────────────────────────┴────┐
                      │                      MySQL Database                       │
                      │  [Tablas de Negocio] examenes, evaluaciones, usuarios     │
                      │  [Memoria LangChain] message_store                        │
                      │  [Memoria RAG SQL]   conocimiento_validado                │
                      └───────────────────────────────────────────────────────────┘
```

---

## 5. Catálogo Detallado de Endpoints REST

### 5.1. `POST /chat`
El endpoint principal de interacción con el agente.
*   **Request Body (`PeticionChat`):**
    ```json
    {
      "session_id": "string (identificador único del chat/usuario)",
      "mensaje": "string (pregunta del usuario)"
    }
    ```
*   **Response (200 OK):**
    ```json
    {
      "status": "ok",
      "respuesta": "string (Respuesta final en lenguaje natural)",
      "corregida_por_gemini": boolean (true si el supervisor intervino)
    }
    ```
*   **Response (Error Interno):** `{"status": "error", "respuesta": "Error interno: ..."}`

### 5.2. `GET /historial/{session_id}`
Recupera el contexto de una conversación para renderizar la interfaz gráfica al recargar la página.
*   **Response (200 OK):**
    ```json
    {
      "status": "ok",
      "historial": [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "¡Hola! ¿En qué puedo ayudarte?"}
      ]
    }
    ```

### 5.3. `GET /chats`
Lista todos los identificadores de sesión únicos que existen en la base de datos.
*   **Response (200 OK):** `{"status": "ok", "chats": ["sesion_1", "sesion_2"]}`

### 5.4. `GET /estado`
Endpoint de Healthcheck. Verifica la disponibilidad de los componentes críticos.
*   **Response (200 OK):**
    ```json
    {
      "status": "ok",
      "modelo": "gemini-3.1-pro-preview",
      "bd_conectada": true,
      "rag_activo": true,
      "herramientas": ["ver_tablas", "ver_esquema", "consultar_base_datos", "buscar_en_documentos"]
    }
    ```

### 5.5. `POST /recargar-pdfs`
Fuerza la re-lectura del directorio `CARPETA_PDFS` y reconstruye el índice vectorial FAISS en memoria. Útil si se añaden nuevos manuales en caliente.
*   **Response (200 OK):** `{"status": "ok", "rag_activo": true}`

---

## 6. Herramientas del Agente (Tools) y Blindaje

Los LLMs a veces fallan al pasar parámetros a las funciones (ej. enviando un diccionario en lugar de un string). Todas las herramientas implementan un **"Blindaje"** al inicio para normalizar la entrada.

1.  **`ver_tablas()`**: Consulta `db.get_usable_table_names()`. Es el punto de entrada para que el LLM descubra el modelo de datos.
2.  **`ver_esquema(tabla)`**: Ejecuta `db.get_table_info()`. Devuelve el DDL (CREATE TABLE) y 3 filas de ejemplo de la tabla solicitada.
3.  **`consultar_base_datos(query_sql)`**:
    *   *Seguridad:* Implementa una validación estricta `query_sql.upper().startswith("SELECT")`. Rechaza cualquier intento de `INSERT`, `UPDATE`, `DELETE` o `DROP`.
    *   *Ejecución:* Lanza la consulta contra MySQL y devuelve el resultado crudo.
4.  **`buscar_en_documentos(pregunta)`**:
    *   *Procesamiento:* Utiliza el `_retriever` de FAISS para buscar los 3 fragmentos (`k=3`) más similares semánticamente a la pregunta.
    *   *Formateo:* Devuelve los textos concatenados indicando `[Fragmento X]`.

---

## 7. Requisitos de Base de Datos (Esquema)

Además de las tablas de negocio (`usuarios`, `examenes`, etc.), el microservicio requiere (o creará automáticamente) las siguientes tablas para su funcionamiento interno:

1.  **`message_store`** (Gestionada automáticamente por `SQLChatMessageHistory`):
    *   Almacena el historial de conversaciones.
    *   Columnas principales: `id`, `session_id`, `message` (JSON con el rol y contenido).
2.  **`conocimiento_validado`** (Debe ser creada manualmente o mediante migraciones):
    *   Almacena pares de Pregunta/Respuesta que han pasado la validación del supervisor. Actúa como memoria a largo plazo y base para el *Few-Shot Prompting*.
    *   Esquema sugerido:
        ```sql
        CREATE TABLE conocimiento_validado (
            id INT AUTO_INCREMENT PRIMARY KEY,
            pregunta TEXT NOT NULL,
            respuesta TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ```

---

## 8. Seguridad y Manejo de Errores

*   **CORS (Cross-Origin Resource Sharing):** Configurado globalmente (`allow_origins=["*"]`) para permitir peticiones desde el API Gateway o frontends en distintos puertos.
*   **Prevención de Inyección SQL:**
    *   El agente no tiene acceso directo a la consola de BD, solo a través de la herramienta `consultar_base_datos`.
    *   La herramienta bloquea por código cualquier instrucción que no empiece por `SELECT`.
    *   *Recomendación DevOps:* El usuario de base de datos configurado en `DATABASE_URL` debe tener permisos de **Solo Lectura (Read-Only)** sobre las tablas de negocio.
*   **Control de Alucinaciones:** El uso de `llm_supervisor.with_structured_output(VeredictoSupervisor)` obliga a Gemini a responder con un esquema Pydantic estricto, garantizando que la evaluación de calidad sea programáticamente procesable.
*   **Manejo de Caídas del LLM:** Si Ollama (Mistral) o Gemini fallan por timeout o cuotas de API, el bloque `try-except` en `/chat` captura la excepción y devuelve un JSON controlado con `status: error`, evitando que FastAPI devuelva un error 500 no formateado.