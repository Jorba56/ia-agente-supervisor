# Sistema de Asistencia IA Híbrido (Multi-Agente)

Este directorio contiene el ecosistema de Inteligencia Artificial desarrollado para el proyecto. Implementa una arquitectura avanzada de **Enrutador Inteligente** y **Supervisor** (patrón *Actor-Crítico* / *Router-Worker*), combinando la privacidad y rapidez de la ejecución local (Ollama) con la capacidad de razonamiento estructurado en la nube (Google Gemini).

El sistema es capaz de auditar código, analizar PDFs de documentación técnica mediante RAG (Retrieval-Augmented Generation) e interactuar directamente con la base de datos MySQL para extraer métricas y datos reales en tiempo real.

##  Estructura del Directorio

* **`api_chatbot.py`**: El núcleo RESTful (FastAPI). Orquesta el sistema Multi-Agente, la conexión a la base de datos MySQL, el motor RAG y el enrutamiento inteligente de consultas.
* **`agente_gemini.py`**: Herramienta CLI auxiliar orientada a la lectura, indexación, refactorización y análisis profundo de código fuente.
* **`documentos/`**: Directorio de ingesta de datos. Los PDFs depositados aquí (manuales, memorias de diseño) son vectorizados automáticamente mediante FAISS para dotar al agente de contexto técnico.
* **`index.html`**: Interfaz web (Frontend) lista para ser servida por la API, proporcionando una experiencia de chat amigable para el usuario final.
* **`*_docs.md`**: Documentación técnica extendida para los scripts individuales.

## Arquitectura del Sistema

1.  **Router (Gemini)**: Analiza la intención del usuario y decide qué herramienta debe ejecutarse (Base de datos, lectura de PDFs, o ninguna).
2.  **Tools (FAISS / MySQL)**: Ejecutan la búsqueda semántica o la consulta SQL extrayendo los datos en bruto (*evidencia real*).
3.  **Worker (Mistral/Llama)**: Modelo de ejecución local que lee la evidencia extraída y redacta una respuesta humana y natural de forma totalmente privada.
4.  **Supervisor (Gemini)**: Audita la respuesta final del Worker comparándola con la evidencia real para eliminar alucinaciones antes de enviarla al cliente.

##  Requisitos Previos

* **Python:** Versión 3.10 o superior.
* **Ollama:** Instalado y corriendo localmente en el puerto `11434`. Debe tener descargado el modelo objetivo (ej. `mistral` o `llama3.2`).
* **Base de Datos:** Un servidor MySQL ejecutándose con la base de datos del proyecto (`examenes`).

*Nota de rendimiento: El procesamiento local del agente worker (Ollama) aprovechará automáticamente la aceleración de hardware disponible en el equipo (como una GPU RTX 2070 Mini y los 16 GB de RAM en Dual Channel), lo que garantiza una generación de texto fluida y una latencia mínima al no depender de colas en la nube para la redacción final.*

##  Instalación y Configuración

1. **Instalar dependencias de Python:**
   Abre una terminal en este directorio e instala las librerías necesarias:
   ```bash
   pip install fastapi uvicorn sqlalchemy pymysql langchain langchain-google-genai langchain-ollama langchain-community pydantic faiss-cpu pypdf
## Configuración del Entorno (Variables)

Asegúrate de que las credenciales en `api_chatbot.py` (sección de configuración) o en tus variables de entorno del sistema coinciden con tu entorno local:

- **`GOOGLE_API_KEY`**: Tu clave de API de Google AI Studio.
- **`DATABASE_URL`**: Cadena de conexión a MySQL (ej. `mysql+pymysql://root:12345@localhost:3306/examenes`).

## Carga de Modelos Locales

Asegúrate de tener el modelo local descargado en tu equipo. Abre una terminal y ejecuta:

```bash
ollama pull mistral
```

# ▶️ Ejecución del Proyecto

Para desplegar el agente y comenzar a utilizar el sistema, sigue estos pasos:

## Paso 1: Iniciar el motor local de IA

Asegúrate de que Ollama está en ejecución en segundo plano. Si no se inicia automáticamente con tu sistema, abre una terminal y ejecuta:

```bash
ollama serve
```

## Paso 2: Iniciar el Servidor API

Abre una nueva terminal en el directorio `ia-proyecto` y levanta el servidor de FastAPI mediante Uvicorn:

```bash
uvicorn api_chatbot:app --host 0.0.0.0 --port 8000 --reload
```

## Paso 3: Acceder a la Interfaz

Una vez que en la terminal veas el mensaje de **Application startup complete** y **RAG cargado**, abre tu navegador web y visita:

```text
http://localhost:8000
```

# 🔄 Mantenimiento y Operaciones Comunes

## Actualizar documentación (PDFs)

Si añades nuevos PDFs a la carpeta `documentos/`, no es necesario reiniciar el servidor por completo. Puedes invocar una recarga del índice vectorial haciendo una petición POST:

```bash
curl -X POST http://localhost:8000/recargar-pdfs
```

## Modificar el modelo local

Si decides cambiar el modelo de redacción (por ejemplo, de Mistral a Llama 3.2), solo necesitas actualizar la variable `model="mistral"` en la inicialización de `ChatOllama` dentro de `api_chatbot.py`.

## ☁️ Alternativa: Despliegue del Motor IA en Railway (Ollama en la Nube)

Durante el desarrollo del proyecto, se validó una arquitectura donde el "Worker" (Ollama) no se ejecuta en la máquina local, sino que se aloja como un microservicio independiente en la nube utilizando **Railway**. Esto es ideal si se desea ejecutar la API en equipos con recursos limitados.

A continuación, se detallan los pasos para replicar este despliegue:

### 1. Creación del Servicio en Railway
1. Inicia sesión en [Railway.app](https://railway.app/) y crea un nuevo proyecto (`New Project`).
2. Selecciona **Deploy from Docker image** (Desplegar desde imagen Docker).
3. Escribe `ollama/ollama` como nombre de la imagen. Railway provisionará un contenedor con el motor base de Ollama.

### 2. Configuración de Almacenamiento (Volúmenes)
Para evitar que el modelo de IA (que pesa varios Gigabytes) se descargue cada vez que el servidor se reinicie, es obligatorio configurar persistencia de datos:
1. Ve a la pestaña **Volumes** dentro de tu nuevo servicio en Railway.
2. Crea un nuevo volumen y móntalo en la ruta interna: `/root/.ollama`.

### 3. Exposición a Internet (Networking)
1. Ve a la pestaña **Settings** (Configuración) del servicio.
2. En la sección **Networking**, haz clic en *Generate Domain*. Esto te dará una URL pública (por ejemplo: `https://ollama-production-xxxx.up.railway.app`).
3. Asegúrate de que el puerto interno expuesto sea el `11434` (el puerto por defecto de la API de Ollama).

### 4. Descarga del Modelo (Pull)
Una vez que el contenedor está corriendo, necesitas descargar el modelo (ej. Mistral o Llama 3.2) dentro de ese servidor:
1. En el dashboard de Railway, ve a tu servicio y abre la consola integrada o ejecuta un comando remoto.
2. Ejecuta el comando de descarga:
   ```bash
   ollama pull mistral