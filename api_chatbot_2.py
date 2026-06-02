from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text
import os
import logging

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import Request
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama, OllamaEmbeddings # <-- ¡Ahora importamos OllamaEmbeddings!
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_community.chat_message_histories import SQLChatMessageHistory
from sqlalchemy import create_engine, MetaData, select
from langchain_core.tools import tool
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv

# ════════════════════════════════════════════════════════════
# # CONFIGURACIÓN
# ════════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

load_dotenv()

URL_BBDD       = os.environ.get("DATABASE_URL")
CARPETA_PDFS   = os.environ.get("PDF_DIR", "documentos")

# URL de tu Ollama en Railway
URL_OLLAMA     = "https://ollama-production-c952.up.railway.app"

# Modelos Locales
MODELO_WORKER     = "mistral"            # El que redacta el texto final
MODELO_SUPERVISOR = "qwen2.5:7b"         # El experto en JSON
MODELO_EMBED      = "nomic-embed-text"   # El experto en vectorizar PDFs localmente
TEMPERATURA       = 0.0

# ════════════════════════════════════════════════════════════
# ESQUEMAS PYDANTIC (ESTRUCTURAS JSON ESTRICTAS)
# ════════════════════════════════════════════════════════════
class PeticionChat(BaseModel):
    session_id: str
    mensaje: str

class DecisionRouter(BaseModel):
    herramienta: str = Field(description="Debe ser EXACTAMENTE una de estas opciones: 'buscar_en_documentos', 'consultar_base_datos', 'ver_tablas', 'ninguna'")
    parametro: str = Field(description="El parámetro para la herramienta. Si la herramienta es 'ninguna', déjalo vacío.")

class VeredictoSupervisor(BaseModel):
    es_valida: bool = Field(description="True si la respuesta es natural y NO contiene código JSON o alucinaciones.")
    respuesta_final: str = Field(description="La respuesta corregida si la original era inválida, o la original si estaba bien.")
    motivo_correccion: str = Field(description="Motivo breve si se corrigió. Vacío si es válida.")

# ════════════════════════════════════════════════════════════
# APP
# ════════════════════════════════════════════════════════════
app = FastAPI(title="Chatbot Agente IA (100% Local & Private Edition)", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ════════════════════════════════════════════════════════════
# A. BASE DE DATOS SQL
# ════════════════════════════════════════════════════════════
try:
    db = SQLDatabase.from_uri(URL_BBDD)
    log.info(f"✅ BD conectada: {URL_BBDD}")
except Exception as e:
    log.error(f"❌ Error conectando a BD: {e}")
    db = None


@tool
def ver_tablas() -> str:
    """Muestra todas las tablas disponibles en la base de datos."""
    if db is None: return "Base de datos no disponible."
    try:
        tablas = db.get_usable_table_names()
        return f"Tablas disponibles: {', '.join(tablas)}"
    except Exception as e:
        return f"Error obteniendo tablas: {e}"

@tool
def ver_esquema(tabla) -> str:
    """Muestra las columnas y estructura de una tabla concreta."""
    if isinstance(tabla, dict): tabla = list(tabla.values())[0]
    if isinstance(tabla, list): tabla = str(tabla[0])
    tabla = str(tabla).strip()
    if db is None: return "Base de datos no disponible."
    try: return db.get_table_info([tabla])
    except Exception as e: return f"Error obteniendo esquema: {e}"

@tool
def consultar_base_datos(query_sql) -> str:
    """Ejecuta una consulta SQL SELECT en la base de datos."""
    if isinstance(query_sql, dict): query_sql = list(query_sql.values())[0]
    if isinstance(query_sql, list): query_sql = " ".join(str(x) for x in query_sql)
    query_sql = str(query_sql).strip()
    if db is None: return "Base de datos no disponible."
    if not query_sql.upper().startswith("SELECT"): return "Error: Solo SELECT."
    try:
        resultado = db.run(query_sql)
        if not resultado: return "La consulta no devolvió resultados."
        return str(resultado)
    except Exception as e: return f"Error ejecutando SQL: {e}"

@tool
def buscar_en_documentos(pregunta) -> str:
    """Busca información teórica en los documentos PDF cargados."""
    if isinstance(pregunta, dict): pregunta = list(pregunta.values())[0]
    if isinstance(pregunta, list): pregunta = " ".join(str(x) for x in pregunta)
    pregunta = str(pregunta).strip()
    if _retriever is None: return "No hay documentos PDF cargados."
    try:
        docs = _retriever.invoke(pregunta)
        if not docs: return "No se encontró información relevante en los documentos."
        return "\n\n".join([f"[Fragmento {i+1}]\n{d.page_content}" for i, d in enumerate(docs)])
    except Exception as e: return f"Error buscando en documentos: {e}"


# ════════════════════════════════════════════════════════════
# B. RAG — LECTURA DE PDFs (100% PRIVADA)
# ════════════════════════════════════════════════════════════
os.makedirs(CARPETA_PDFS, exist_ok=True)
_retriever = None

def cargar_pdfs() -> None:
    global _retriever
    try:
        loader = PyPDFDirectoryLoader(CARPETA_PDFS)
        docs = loader.load()
        if not docs:
            log.info("📂 Carpeta 'documentos' vacía — RAG desactivado.")
            return

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = splitter.split_documents(docs)

        # Utilizamos OllamaEmbeddings en lugar de Google
        embeddings = OllamaEmbeddings(model=MODELO_EMBED, base_url=URL_OLLAMA)

        primer_split = splits[0]
        vectorstore = FAISS.from_texts([primer_split.page_content], embeddings, metadatas=[primer_split.metadata])
        for split in splits[1:]:
            vectorstore.add_texts([split.page_content], metadatas=[split.metadata])

        _retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
        log.info(f"✅ RAG Privado cargado: {len(docs)} PDFs → {len(splits)} fragmentos")
    except Exception as e:
        log.error(f"❌ Error cargando PDFs: {e}")
        _retriever = None

cargar_pdfs()

def obtener_ejemplos_similares(pregunta: str, limite: int = 3) -> str:
    if db is None: return ""
    try:
        engine = create_engine(URL_BBDD)
        palabras = [p for p in pregunta.split() if len(p) > 3]
        if not palabras: return ""
        with engine.connect() as conn:
            meta = MetaData()
            meta.reflect(bind=engine)
            if 'conocimiento_validado' not in meta.tables: return ""
            like_clauses = " OR ".join([f"pregunta LIKE :p{i}" for i in range(len(palabras[:3]))])
            params = {f"p{i}": f"%{p}%" for i, p in enumerate(palabras[:3])}
            params["limite"] = limite
            query = text(f"SELECT pregunta, respuesta FROM conocimiento_validado WHERE {like_clauses} ORDER BY id DESC LIMIT :limite")
            rows = conn.execute(query, params).fetchall()
            if not rows: return ""
            return "\n\nEJEMPLOS DE RESPUESTAS CORRECTAS ANTERIORES:\n" + "\n".join([f"P: {r[0]}\nR: {r[1]}" for r in rows]) + "\n"
    except Exception as e:
        return ""


# ════════════════════════════════════════════════════════════
# C. INSTANCIAS DE OLLAMA (WORKER, ROUTER Y SUPERVISOR)
# ════════════════════════════════════════════════════════════

# 1. El Worker (El que redacta - Mistral)
llm_worker = ChatOllama(
    base_url=URL_OLLAMA,
    model=MODELO_WORKER,
    temperature=TEMPERATURA,
    timeout=240.0
)

# 2. El Cerebro Estructurado (Router y Supervisor - Qwen2.5)
llm_supervisor = ChatOllama(
    base_url=URL_OLLAMA,
    model=MODELO_SUPERVISOR,
    temperature=TEMPERATURA,
    timeout=240.0
)

# Forzamos a que Ollama devuelva JSON estrictos basados en nuestras clases Pydantic
enrutador = llm_supervisor.with_structured_output(DecisionRouter)
validador = llm_supervisor.with_structured_output(VeredictoSupervisor)

log.info(f"✅ Agentes Locales Creados: Worker({MODELO_WORKER}) | Supervisor({MODELO_SUPERVISOR})")

herramientas = [ver_tablas, ver_esquema, consultar_base_datos, buscar_en_documentos]

# ════════════════════════════════════════════════════════════
# D. CONFIGURACION DE EMAILS
# ════════════════════════════════════════════════════════════

def enviar_alerta_gmail(asunto: str, mensaje_ia: str):
    """Función proactiva para que el agente te envíe notificaciones por correo."""
    remitente = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_PASS")
    destinatario = remitente  # Te lo envía a ti mismo

    if not remitente or not password:
        log.error("⚠️ Faltan credenciales GMAIL_USER o GMAIL_PASS en el .env")
        return False

    msg = MIMEMultipart()
    msg['From'] = f"🤖 Agente IA (Local) <{remitente}>"
    msg['To'] = destinatario
    msg['Subject'] = asunto
    msg.attach(MIMEText(mensaje_ia, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente, password)
        server.send_message(msg)
        server.quit()
        log.info(f"✉️ ✅ Correo enviado con éxito: {asunto}")
        return True
    except Exception as e:
        log.error(f"✉️ ❌ Error al enviar correo: {e}")
        return False

enviar_alerta_gmail("Prueba de IA", "El sistema de notificaciones está operativo.")

# ════════════════════════════════════════════════════════════
# D. ENDPOINTS
# ════════════════════════════════════════════════════════════
def obtener_memoria(session_id: str):
    return SQLChatMessageHistory(session_id=session_id, connection=URL_BBDD)

@app.get("/", response_class=HTMLResponse)
def leer_interfaz():
    ruta_html = os.path.join(os.path.dirname(__file__), "index.html")
    try:
        with open(ruta_html, "r", encoding="utf-8") as f: return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>index.html no encontrado</h1>", status_code=404)

def guardar_respuesta_validada(pregunta: str, respuesta_final: str):
    if db is None: return
    try:
        query = text("INSERT INTO conocimiento_validado (pregunta, respuesta) VALUES (:p, :r)")
        with db._engine.connect() as conn:
            conn.execute(query, {"p": pregunta, "r": respuesta_final})
            conn.commit()
    except Exception as e:
        log.error(f"Error guardando conocimiento: {e}")


@app.post("/github-webhook")
async def webhook_github(request: Request):
    """Escucha commits de GitHub y dispara la auditoría proactiva."""
    try:
        payload = await request.json()

        # Ignoramos si no es un evento de subida de código (push)
        if "commits" not in payload:
            return {"status": "ignored", "reason": "No es un push"}

        repo_name = payload["repository"]["name"]

        # Extraemos qué archivos has tocado
        archivos_cambiados = []
        for commit in payload["commits"]:
            archivos_cambiados.extend(commit.get("added", []))
            archivos_cambiados.extend(commit.get("modified", []))

        if not archivos_cambiados:
            return {"status": "ok", "message": "Sin archivos para auditar."}

        log.info(f"🔍 Webhook activado. El agente va a auditar: {archivos_cambiados}")

        # 1. Le pedimos a Mistral que audite el primer archivo cambiado
        archivo_objetivo = archivos_cambiados[0]
        prompt_auditoria = f"""
        Eres un auditor de código senior. Se acaba de modificar el archivo: '{archivo_objetivo}' 
        en el repositorio '{repo_name}'.
        
        Redacta un informe de 3 puntos sobre qué vulnerabilidades de seguridad, 
        fallos de rendimiento o malas prácticas buscarías específicamente 
        al revisar un archivo con ese nombre y extensión. Sé directo y técnico.
        """

        # El Worker (Mistral) procesa la información
        respuesta_ia = llm_worker.invoke(prompt_auditoria).content

        # 2. El agente te envía el correo automáticamente
        asunto_correo = f"🚨 Auditoría de IA: {archivo_objetivo} modificado"
        enviar_alerta_gmail(asunto_correo, respuesta_ia)

        return {"status": "ok", "archivos_auditados": archivos_cambiados}

    except Exception as e:
        log.error(f"Error en webhook: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/chat")
def chatear(peticion: PeticionChat):
    try:
        if not peticion.mensaje.strip(): return {"status": "error", "respuesta": "Mensaje vacío."}

        memoria = obtener_memoria(peticion.session_id)
        ejemplos = obtener_ejemplos_similares(peticion.mensaje)

        # ---------------------------------------------------------
        # PASO 1: Ollama Router decide con Pydantic (Sin Regex!)
        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # PASO 1: Ollama Router decide con Pydantic (Sin Regex!)
        # ---------------------------------------------------------

        # Extraemos el esquema real de la BD en texto plano para que el router no trabaje a ciegas
        esquema_bd = ""
        if db is not None:
            try:
                esquema_bd = db.get_table_info()
            except Exception as e:
                esquema_bd = f"Error obteniendo esquema: {e}"

        prompt_decision = f"""
        Eres un router inteligente. Tu única misión es clasificar la intención de esta petición:
        Petición: "{peticion.mensaje}"

        REGLAS MILITARES DE CLASIFICACIÓN:
        1. SALUDOS O CHARLA: Si el usuario dice "Hola" o charla normal, herramienta: "ninguna", parametro: "".
        2. TEORÍA Y MANUALES: Si pregunta conceptos o PDFs, herramienta: "buscar_en_documentos", parametro: la pregunta completa.
        3. DATOS REALES: Si pregunta por exámenes, usuarios o notas, herramienta: "consultar_base_datos".
        
        !!! MUY IMPORTANTE PARA DATOS REALES !!!
        Si usas "consultar_base_datos", debes escribir el SQL exacto basándote ÚNICAMENTE en este esquema real de la base de datos:
        {esquema_bd}
        
        EJEMPLOS DE ENRUTAMIENTO CORRECTO:
        - "Hola" -> herramienta: "ninguna", parametro: ""
        - "¿Cómo declaro una variable?" -> herramienta: "buscar_en_documentos", parametro: "¿Cómo declaro una variable?"
        - "¿Cuál es el título del examen 9?" -> herramienta: "consultar_base_datos", parametro: "SELECT nombre_columna FROM nombre_tabla_real WHERE id=9;"
        """

        try:
            decision = enrutador.invoke(prompt_decision)
            herramienta_elegida = decision.herramienta
            parametro = decision.parametro
        except Exception as e:
            log.warning(f"Error en estructuración del router: {e}")
            herramienta_elegida = "ninguna"
            parametro = ""


        log.info(f"[ROUTER OLLAMA] Herramienta: {herramienta_elegida} | Param: {parametro[:100]}")

        # ---------------------------------------------------------
        # PASO 2: Ejecución de la herramienta
        # ---------------------------------------------------------
        resultado_herramienta = ""
        if herramienta_elegida == "buscar_en_documentos":
            res = buscar_en_documentos.invoke({"pregunta": parametro})
            resultado_herramienta = res if isinstance(res, str) else "\n".join(str(r) for r in res)
        elif herramienta_elegida == "consultar_base_datos":
            res = consultar_base_datos.invoke({"query_sql": parametro})
            resultado_herramienta = res if isinstance(res, str) else "\n".join(str(r) for r in res)
        elif herramienta_elegida == "ver_tablas":
            res = ver_tablas.invoke({})
            resultado_herramienta = res if isinstance(res, str) else "\n".join(str(r) for r in res)

        log.info(f"[HERRAMIENTA] {str(resultado_herramienta)[:100]}...")

        # ---------------------------------------------------------
        # PASO 3: Ollama Worker redacta la respuesta
        # ---------------------------------------------------------
        historial_texto = "".join([f"{'Usuario' if isinstance(m, HumanMessage) else 'Asistente'}: {m.content}\n" for m in list(memoria.messages)[-6:]])

        prompt_respuesta = f"""Eres un asistente experto.
        {f'Historial:{chr(10)}{historial_texto}' if historial_texto else ''}
        Pregunta: {peticion.mensaje}
        Fuente de verdad: {resultado_herramienta if resultado_herramienta else 'No hay fuentes.'}
        
        Responde SOLO usando la fuente de verdad. No muestres JSON, ni tu proceso interno.
        """
        respuesta_borrador = llm_worker.invoke(prompt_respuesta).content

        # ---------------------------------------------------------
        # PASO 4: Ollama Supervisor audita usando Pydantic
        # ---------------------------------------------------------
        prompt_validacion = f"""
        Eres el supervisor de calidad.
        Evidencia extraída: "{str(resultado_herramienta)[:500]}"
        Respuesta generada: "{respuesta_borrador}"
        
        ¿La respuesta usa solo la evidencia y no contiene formatos JSON o menciones a herramientas?
        Corrige la respuesta si es necesario.
        """
        try:
            veredicto = validador.invoke(prompt_validacion)
            respuesta_final = veredicto.respuesta_final
            es_valida = veredicto.es_valida
            motivo = veredicto.motivo_correccion
        except Exception as e:
            log.warning(f"Error en el supervisor Ollama: {e}")
            respuesta_final = respuesta_borrador
            es_valida = True
            motivo = ""

        if not es_valida:
            log.warning(f"[SUPERVISOR] Corregido. Motivo: {motivo}")

        # Guardado en BBDD
        memoria.add_user_message(peticion.mensaje)
        memoria.add_ai_message(respuesta_final)
        guardar_respuesta_validada(peticion.mensaje, respuesta_final)

        return {
            "status": "ok",
            "respuesta": respuesta_final,
            "corregida_por_supervisor": not es_valida
        }

    except Exception as e:
        log.error(f"Error general en /chat: {e}")
        return {"status": "error", "respuesta": f"Error interno: {str(e)}"}

@app.get("/historial/{session_id}")
def obtener_historial(session_id: str):
    memoria = obtener_memoria(session_id)
    mensajes = [{"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content} for m in memoria.messages]
    return {"status": "ok", "historial": mensajes}

@app.get("/chats")
def listar_chats():
    try:
        engine = create_engine(URL_BBDD)
        meta = MetaData()
        meta.reflect(bind=engine)
        if 'message_store' not in meta.tables: return {"status": "ok", "chats": []}
        message_store = meta.tables['message_store']
        with engine.connect() as conn:
            chats = [row[0] for row in conn.execute(select(message_store.c.session_id).distinct()).fetchall()]
            return {"status": "ok", "chats": chats}
    except Exception as e: return {"status": "error", "respuesta": str(e)}

@app.get("/estado")
def estado():
    return {
        "status": "ok",
        "worker": MODELO_WORKER,
        "supervisor": MODELO_SUPERVISOR,
        "bd_conectada": db is not None,
        "rag_activo": _retriever is not None
    }

@app.post("/recargar-pdfs")
def recargar_pdfs():
    cargar_pdfs()
    return {"status": "ok", "rag_activo": _retriever is not None}