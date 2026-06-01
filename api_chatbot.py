from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, Field
from sqlalchemy import text
import os
import logging

from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from langchain_community.chat_message_histories import SQLChatMessageHistory
from sqlalchemy import create_engine, MetaData, select
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.utilities import SQLDatabase

# ════════════════════════════════════════════════════════════
# # CONFIGURACIÓN
# ════════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyBCuAesU-c9qJu3ruf2FHqM-adWxUB7pOw")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

URL_BBDD       = os.environ.get("DATABASE_URL", "mysql+pymysql://root:12345@localhost:3306/examenes")
CARPETA_PDFS   = os.environ.get("PDF_DIR", "documentos")
MODELO_LLM     = "gemini-3.1-pro-preview"        # Estable y rápido
MODELO_EMBED   = "models/gemini-embedding-2"       # Último modelo estable de Google
TEMPERATURA    = 0.7

# ════════════════════════════════════════════════════════════
# APP
# ════════════════════════════════════════════════════════════
app = FastAPI(title="Chatbot Agente IA", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PeticionChat(BaseModel):
    session_id: str
    mensaje: str


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
    """Muestra todas las tablas disponibles en la base de datos.
    Llama a esta herramienta primero para saber qué tablas existen."""
    if db is None:
        return "Base de datos no disponible."
    try:
        tablas = db.get_usable_table_names()
        return f"Tablas disponibles: {', '.join(tablas)}"
    except Exception as e:
        return f"Error obteniendo tablas: {e}"


@tool
def ver_esquema(tabla) -> str:
    """Muestra las columnas y estructura de una tabla concreta."""
    # --- BLINDAJE ---
    if isinstance(tabla, dict): tabla = list(tabla.values())[0]
    if isinstance(tabla, list): tabla = str(tabla[0])
    tabla = str(tabla).strip()
    # ----------------

    if db is None: return "Base de datos no disponible."
    try:
        return db.get_table_info([tabla])
    except Exception as e:
        return f"Error obteniendo esquema de '{tabla}': {e}"


@tool
def consultar_base_datos(query_sql) -> str:
    """Ejecuta una consulta SQL SELECT en la base de datos."""
    # --- BLINDAJE ---
    if isinstance(query_sql, dict): query_sql = list(query_sql.values())[0]
    if isinstance(query_sql, list): query_sql = " ".join(str(x) for x in query_sql)
    query_sql = str(query_sql).strip()
    # ----------------

    if db is None: return "Base de datos no disponible."
    if not query_sql.upper().startswith("SELECT"):
        return "Error: Solo se permiten consultas SELECT por seguridad."
    try:
        resultado = db.run(query_sql)
        if not resultado: return "La consulta no devolvió resultados."
        return str(resultado)
    except Exception as e:
        return f"Error ejecutando SQL: {e}"


@tool
def buscar_en_documentos(pregunta) -> str:
    """Busca información teórica en los documentos PDF cargados."""
    # --- BLINDAJE ---
    if isinstance(pregunta, dict): pregunta = list(pregunta.values())[0]
    if isinstance(pregunta, list): pregunta = " ".join(str(x) for x in pregunta)
    pregunta = str(pregunta).strip()
    # ----------------

    if _retriever is None:
        return "No hay documentos PDF cargados. Añade PDFs y reinicia."
    try:
        docs = _retriever.invoke(pregunta)
        if not docs: return "No se encontró información relevante en los documentos."
        return "\n\n".join([f"[Fragmento {i+1}]\n{d.page_content}" for i, d in enumerate(docs)])
    except Exception as e:
        return f"Error buscando en documentos: {e}"


# ════════════════════════════════════════════════════════════
# B. RAG — LECTURA DE PDFs
# ════════════════════════════════════════════════════════════
os.makedirs(CARPETA_PDFS, exist_ok=True)
_retriever = None



def cargar_pdfs() -> None:
    """Carga los PDFs de la carpeta documentos/ y construye el índice vectorial."""
    global _retriever
    try:
        loader = PyPDFDirectoryLoader(CARPETA_PDFS)
        docs = loader.load()

        if not docs:
            log.info("📂 Carpeta 'documentos' vacía — RAG desactivado.")
            return

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = splitter.split_documents(docs)

        embeddings = GoogleGenerativeAIEmbeddings(
            model=MODELO_EMBED,
            task_type="retrieval_document",
        )

        # Creamos el vectorstore fragmento a fragmento para evitar el límite de batch
        log.info(f"📄 Procesando {len(splits)} fragmentos uno a uno...")

        primer_split = splits[0]
        vectorstore = FAISS.from_texts(
            [primer_split.page_content],
            embeddings,
            metadatas=[primer_split.metadata]
        )

        # Añadimos el resto de uno en uno
        for split in splits[1:]:
            vectorstore.add_texts(
                [split.page_content],
                metadatas=[split.metadata]
            )

        _retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
        log.info(f"✅ RAG cargado: {len(docs)} PDFs → {len(splits)} fragmentos")

    except Exception as e:
        log.error(f"❌ Error cargando PDFs: {e}")
        _retriever = None



cargar_pdfs()


def obtener_ejemplos_similares(pregunta: str, limite: int = 3) -> str:
    """Busca en conocimiento_validado ejemplos parecidos a la pregunta actual."""
    if db is None:
        return ""
    try:
        engine = create_engine(URL_BBDD)
        # Busca por palabras clave de la pregunta
        palabras = [p for p in pregunta.split() if len(p) > 3]
        if not palabras:
            return ""

        with engine.connect() as conn:
            # Comprueba si la tabla existe
            meta = MetaData()
            meta.reflect(bind=engine)
            if 'conocimiento_validado' not in meta.tables:
                return ""

            # Busca ejemplos que contengan palabras de la pregunta
            like_clauses = " OR ".join([f"pregunta LIKE :p{i}" for i in range(len(palabras[:3]))])
            params = {f"p{i}": f"%{p}%" for i, p in enumerate(palabras[:3])}
            params["limite"] = limite

            query = text(f"""
                SELECT pregunta, respuesta 
                FROM conocimiento_validado 
                WHERE {like_clauses}
                ORDER BY id DESC
                LIMIT :limite
            """)
            rows = conn.execute(query, params).fetchall()

            if not rows:
                return ""

            ejemplos = "\n".join([
                f"P: {r[0]}\nR: {r[1]}" for r in rows
            ])
            return f"\n\nEJEMPLOS DE RESPUESTAS CORRECTAS ANTERIORES (aprende de estos patrones):\n{ejemplos}\n"

    except Exception as e:
        log.warning(f"No se pudieron cargar ejemplos: {e}")
        return ""


@tool
def buscar_en_documentos(pregunta: str) -> str:
    """Busca información teórica en los documentos PDF cargados.
    Usa esta herramienta para preguntas sobre conceptos, guías, manuales o documentación.
    NO uses esta herramienta para datos de la base de datos.

    Args:
        pregunta: La pregunta o concepto a buscar en los documentos.
    """
    if _retriever is None:
        return "No hay documentos PDF cargados. Añade PDFs a la carpeta 'documentos' y reinicia el servidor."
    try:
        docs = _retriever.invoke(pregunta)
        if not docs:
            return "No se encontró información relevante en los documentos."
        fragmentos = [f"[Fragmento {i+1}]\n{d.page_content}" for i, d in enumerate(docs)]
        return "\n\n".join(fragmentos)
    except Exception as e:
        return f"Error buscando en documentos: {e}"


# ════════════════════════════════════════════════════════════
# C. AGENTE LangGraph
# ════════════════════════════════════════════════════════════
llm = ChatOllama(
    base_url="https://ollama-production-c952.up.railway.app", # La ruta interna de tu cerebro en Railway
    model="mistral",
    temperature=0.0,
    timeout=240.0
)
llm_supervisor= ChatGoogleGenerativeAI(model=MODELO_LLM, temperature=0)

class VeredictoSupervisor(BaseModel):
    es_valida: bool = Field(description="True si la respuesta responde a la pregunta sin inventar datos ni errores técnicos. False si es incorrecta.")
    respuesta_final: str = Field(description="Si es válida, devuelve la respuesta original. Si no, escribe la respuesta correcta solucionando los errores.")
    motivo_correccion: str = Field(description="Si la corregiste, explica brevemente al administrador por qué lo hiciste. Si es válida, déjalo vacío.")

# Creamos una versión de Gemini que SOLO puede responder con este esquema JSON
validador = llm_supervisor.with_structured_output(VeredictoSupervisor)

herramientas = [ver_tablas, ver_esquema, consultar_base_datos, buscar_en_documentos]

SYSTEM_PROMPT = """Eres un asistente corporativo experto.
Tu objetivo es responder a las preguntas del usuario usando tus herramientas.

REGLAS ESTRICTAS — DEBES SEGUIRLAS SIN EXCEPCIÓN:
1. Cuando el usuario haga una pregunta, USA LAS HERRAMIENTAS INMEDIATAMENTE. No preguntes si puedes buscar, BUSCA.
2. Para preguntas sobre datos de usuarios, notas o exámenes: usa ver_tablas → ver_esquema → consultar_base_datos.
3. Para preguntas sobre documentación, reglas, mecánicas o cualquier tema teórico: usa buscar_en_documentos DIRECTAMENTE.
4. NUNCA pidas permiso para usar una herramienta. NUNCA preguntes "¿quieres que busque?". BUSCA Y RESPONDE.
5. NUNCA muestres JSON al usuario. Usa las herramientas en silencio y responde en lenguaje natural.
6. Si no encuentras información tras usar las herramientas, dilo claramente.

FLUJO OBLIGATORIO:
Usuario pregunta → Tú usas herramienta → Lees resultado → Respondes en español natural.
"""

agente = create_react_agent(
    model=llm,
    tools=herramientas,
    prompt=SystemMessage(content=SYSTEM_PROMPT)
)


log.info(f"✅ Supervisor creado con modelo {MODELO_LLM} y {len(herramientas)} herramientas")


# ════════════════════════════════════════════════════════════
# D. ENDPOINTS
# ════════════════════════════════════════════════════════════
def obtener_memoria(session_id: str):
    # Conecta directamente con tu URL_BBDD y agrupa los mensajes por session_id
    return SQLChatMessageHistory(
        session_id=session_id,
        connection=URL_BBDD
    )

@app.get("/", response_class=HTMLResponse)
def leer_interfaz():
    """Sirve la interfaz web."""
    ruta_html = os.path.join(os.path.dirname(__file__), "index.html")
    try:
        with open(ruta_html, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>index.html no encontrado</h1>", status_code=404)

def guardar_respuesta_validada(pregunta: str, respuesta_final: str):
    """Guarda la pregunta y la respuesta aprobada en la memoria a largo plazo."""
    if db is None: return
    try:
        query = text("INSERT INTO conocimiento_validado (pregunta, respuesta) VALUES (:p, :r)")
        engine = db._engine
        with engine.connect() as conn:
            conn.execute(query, {"p": pregunta, "r": respuesta_final})
            conn.commit()
    except Exception as e:
        log.error(f"Error guardando conocimiento validado: {e}")

@app.post("/chat")
def chatear(peticion: PeticionChat):
    try:
        if not peticion.mensaje.strip():
            return {"status": "error", "respuesta": "Mensaje vacío."}

        memoria = obtener_memoria(peticion.session_id)
        ejemplos = obtener_ejemplos_similares(peticion.mensaje)

        # PASO 1: Gemini decide qué herramienta usar y con qué parámetros
        prompt_decision = f"""
        Eres un router inteligente. Analiza la pregunta del usuario y decide qué herramienta usar.
        
        Herramientas disponibles:
        - buscar_en_documentos(pregunta): Para preguntas sobre documentación, PDFs, mecánicas, reglas, conceptos técnicos
        - consultar_base_datos(query_sql): Para datos reales de la BD (notas, alumnos, exámenes, registros)
        - ver_tablas(): Para conocer qué tablas existen en la BD
        - ninguna: Si la pregunta es una conversación general sin necesidad de datos
        
        Pregunta: "{peticion.mensaje}"
        
        Responde ÚNICAMENTE con este JSON exacto, sin texto adicional:
        {{"herramienta": "nombre_herramienta", "parametro": "valor del parámetro"}}
        
        Ejemplos:
        - pregunta sobre PDFs → {{"herramienta": "buscar_en_documentos", "parametro": "la pregunta completa"}}
        - pregunta sobre datos → {{"herramienta": "consultar_base_datos", "parametro": "SELECT ..."}}
        - saludo → {{"herramienta": "ninguna", "parametro": ""}}
        """
        decision_raw = llm_supervisor.invoke(prompt_decision)

        # Extrae el texto correctamente sea string o lista
        if isinstance(decision_raw.content, str):
            texto_decision = decision_raw.content
        elif isinstance(decision_raw.content, list):
            texto_decision = " ".join(
                b.get("text", "") for b in decision_raw.content
                if isinstance(b, dict)
            )
        else:
            texto_decision = str(decision_raw.content)

        log.info(f"[ROUTER RAW] {texto_decision[:200]}")

        import json, re
        match = re.search(r'\{.*?\}', texto_decision, re.DOTALL)
        try:
            decision = json.loads(match.group(0)) if match else {"herramienta": "ninguna", "parametro": ""}
        except json.JSONDecodeError:
            decision = {"herramienta": "ninguna", "parametro": ""}


        herramienta_elegida = decision.get("herramienta", "ninguna")
        parametro = decision.get("parametro", "")

        log.info(f"[ROUTER] Herramienta elegida: {herramienta_elegida} | Parámetro: {parametro[:100]}")

        # PASO 2: Ejecuta la herramienta elegida
        # PASO 2: Ejecuta la herramienta elegida
        resultado_herramienta = ""
        if herramienta_elegida == "buscar_en_documentos":
            res = buscar_en_documentos.invoke({"pregunta": parametro})
            log.info(f"[DEBUG] Tipo resultado buscar_en_documentos: {type(res)} | Valor: {str(res)[:200]}")
            resultado_herramienta = res if isinstance(res, str) else "\n".join(str(r) for r in res)
        elif herramienta_elegida == "consultar_base_datos":
            res = consultar_base_datos.invoke({"query_sql": parametro})
            log.info(f"[DEBUG] Tipo resultado consultar_base_datos: {type(res)} | Valor: {str(res)[:200]}")
            resultado_herramienta = res if isinstance(res, str) else "\n".join(str(r) for r in res)
        elif herramienta_elegida == "ver_tablas":
            res = ver_tablas.invoke({})
            log.info(f"[DEBUG] Tipo resultado ver_tablas: {type(res)} | Valor: {str(res)[:200]}")
            resultado_herramienta = res if isinstance(res, str) else "\n".join(str(r) for r in res)

        log.info(f"[HERRAMIENTA] Resultado: {str(resultado_herramienta)[:200]}")

        # PASO 3: Mistral redacta la respuesta final con los datos reales
        historial_texto = ""
        for msg in list(memoria.messages)[-6:]:  # Últimos 3 turnos
            rol = "Usuario" if isinstance(msg, HumanMessage) else "Asistente"
            historial_texto += f"{rol}: {msg.content}\n"

        prompt_respuesta = f"""Eres un asistente experto. Responde en español de forma clara y natural.

        {f'Historial reciente:{chr(10)}{historial_texto}' if historial_texto else ''}
        {f'Ejemplos de respuestas correctas anteriores:{chr(10)}{ejemplos}' if ejemplos else ''}
        
        Pregunta del usuario: {peticion.mensaje}
        
        {f'Información encontrada:{chr(10)}{resultado_herramienta}' if resultado_herramienta else 'No se encontró información específica en las fuentes disponibles.'}
        
        Instrucciones:
        - Responde basándote SOLO en la información encontrada
        - No muestres JSON, código técnico ni menciones las herramientas
        - Si no hay información suficiente, dilo claramente
        - Sé conciso y directo
        """
        respuesta_borrador = llm.invoke(prompt_respuesta).content

        # PASO 4: Gemini supervisa la respuesta
        prompt_validacion = f"""
        Supervisor de calidad. Valida esta respuesta.
        
        Pregunta: "{peticion.mensaje}"
        Información de fuente: "{str(resultado_herramienta)[:500]}"
        Respuesta del asistente: "{respuesta_borrador}"
        
        Valida si la respuesta es correcta y natural. Si contiene JSON, código técnico expuesto, 
        o datos inventados no presentes en la fuente, corrígela.
        """
        veredicto = validador.invoke(prompt_validacion)

        respuesta_final = veredicto.respuesta_final
        if not veredicto.es_valida:
            log.warning(f"[SUPERVISOR] Corregido. Motivo: {veredicto.motivo_correccion}")
            log.warning(f"[SUPERVISOR] Borrador: {respuesta_borrador[:200]}")

        memoria.add_user_message(peticion.mensaje)
        memoria.add_ai_message(respuesta_final)
        guardar_respuesta_validada(peticion.mensaje, respuesta_final)

        return {
            "status": "ok",
            "respuesta": respuesta_final,
            "corregida_por_gemini": not veredicto.es_valida
        }

    except Exception as e:
        log.error(f"Error en /chat: {e}")
        return {"status": "error", "respuesta": f"Error interno: {str(e)}"}

@app.get("/historial/{session_id}")
def obtener_historial(session_id: str):
    """Devuelve los mensajes previos de un chat para pintarlos al cargar la web."""
    memoria = obtener_memoria(session_id)
    mensajes = []
    for m in memoria.messages:
        # Convertimos los objetos de LangChain a diccionarios simples para el frontend
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        mensajes.append({"role": role, "content": m.content})
    return {"status": "ok", "historial": mensajes}

@app.get("/chats")
def listar_chats():
    """Busca en MySQL todos los IDs de sesión (chats) creados hasta la fecha."""
    try:
        engine = create_engine(URL_BBDD)
        metadata = MetaData()
        metadata.reflect(bind=engine)

        # Si la tabla aún no existe (porque no hay chats), devolvemos lista vacía
        if 'message_store' not in metadata.tables:
            return {"status": "ok", "chats": []}

        message_store = metadata.tables['message_store']
        with engine.connect() as conn:
            query = select(message_store.c.session_id).distinct()
            chats = [row[0] for row in conn.execute(query).fetchall()]
            return {"status": "ok", "chats": chats}
    except Exception as e:
        return {"status": "error", "respuesta": str(e)}

@app.get("/estado")
def estado():
    return {
        "status": "ok",
        "modelo": MODELO_LLM,
        "bd_conectada": db is not None,
        "rag_activo": _retriever is not None,
        "herramientas": [t.name for t in herramientas]
    }


@app.post("/recargar-pdfs")
def recargar_pdfs():

    cargar_pdfs()
    return {
        "status": "ok",
        "rag_activo": _retriever is not None
    }