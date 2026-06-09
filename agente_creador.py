import os
from typing import List, TypedDict
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic # (Si vas a usar Claude en el futuro)
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END

# ════════════════════════════════════════════════════════════
# 1. CONFIGURACIÓN Y ENTORNO
# ════════════════════════════════════════════════════════════
load_dotenv()
WORKSPACE = "./proyectos_generados"
os.makedirs(WORKSPACE, exist_ok=True)

# ════════════════════════════════════════════════════════════
# 2. PYDANTIC: EL "PLANO" DEL ARQUITECTO
# ════════════════════════════════════════════════════════════
class ArchivoProyectado(BaseModel):
    ruta_relativa: str = Field(description="Ruta y nombre del archivo. Ej: src/main/java/com/app/Main.java")
    descripcion_logica: str = Field(description="Qué debe hacer exactamente este archivo, imports y dependencias.")

class PlanProyecto(BaseModel):
    archivos: List[ArchivoProyectado] = Field(description="Lista de todos los archivos necesarios para construir el proyecto.")

# ════════════════════════════════════════════════════════════
# 3. FÁBRICA DE MODELOS (Configurabilidad Local/Remota)
# ════════════════════════════════════════════════════════════
def obtener_modelo(entorno: str, nombre_modelo: str):
    if entorno == "gemini":
        return ChatGoogleGenerativeAI(model=nombre_modelo, temperature=0)
    elif entorno == "local":
        # Apuntando a tu Ollama local o de Railway
        return ChatOllama(
            base_url="https://ollama-production-c952.up.railway.app",
            model=nombre_modelo,
            temperature=0,
            timeout=3000,        # ← 5 minutos
            num_ctx=8192,       # ← más contexto para archivos grandes
        )

    elif entorno == "claude":
        return ChatAnthropic(model_name=nombre_modelo, temperature=0)
    else:
        raise ValueError(f"Entorno {entorno} no soportado")

# --- ASIGNACIÓN DE ROLES ---
arquitecto_llm = obtener_modelo("gemini", "gemini-3.1-pro-preview")
programador_llm = obtener_modelo("local", "qwen3.5:4b")

# Forzamos al Arquitecto a devolver SÓLO la estructura JSON
arquitecto_json = arquitecto_llm.with_structured_output(PlanProyecto)

# ════════════════════════════════════════════════════════════
# 4. HERRAMIENTAS (LAS "MANOS" DEL PROGRAMADOR)
# ════════════════════════════════════════════════════════════
@tool
def crear_archivo(ruta_relativa: str, contenido: str) -> str:
    """Guarda físicamente el código generado en el disco duro del ordenador."""
    try:
        ruta_completa = os.path.abspath(os.path.join(WORKSPACE, ruta_relativa))
        # Blindaje de seguridad para que la IA no escriba donde no debe
        if not ruta_completa.startswith(os.path.abspath(WORKSPACE)):
            return f"Error: Permiso denegado para escribir fuera de {WORKSPACE}"

        os.makedirs(os.path.dirname(ruta_completa), exist_ok=True)
        with open(ruta_completa, "w", encoding="utf-8") as f:
            f.write(contenido)
        return f"✅ Archivo creado: {ruta_relativa}"
    except Exception as e:
        return f"❌ Error guardando {ruta_relativa}: {str(e)}"

# Le damos la herramienta al programador
programador_con_herramientas = programador_llm.bind_tools([crear_archivo])

# ════════════════════════════════════════════════════════════
# 5. EL FLUJO LANGGRAPH (AGENTES)
# ════════════════════════════════════════════════════════════
class EstadoProyecto(TypedDict):
    peticion: str
    plan: PlanProyecto
    logs: List[str]

def nodo_arquitecto(state: EstadoProyecto):
    print("\n🧠 [ARQUITECTO] Diseñando la arquitectura del proyecto...")
    prompt = f"Eres un Arquitecto de Software Senior. Diseña la estructura completa para esta petición: '{state['peticion']}'"

    plan_generado = arquitecto_json.invoke(prompt)
    print(f"✅ [ARQUITECTO] Plan maestro creado con {len(plan_generado.archivos)} archivos.")

    return {"plan": plan_generado}

def nodo_programador(state: EstadoProyecto):
    plan = state["plan"]
    print("\n💻 [PROGRAMADOR] Iniciando la codificación...")

    # El programador recorre el JSON y fabrica archivo por archivo
    for archivo in plan.archivos:
        print(f"   ⏳ Escribiendo código para: {archivo.ruta_relativa}...")
        prompt_codigo = f"""
        Eres un programador experto. Tu tarea es generar el código fuente exacto para este archivo.
        Archivo a crear: {archivo.ruta_relativa}
        Descripción técnica: {archivo.descripcion_logica}
        
        Usa la herramienta 'crear_archivo' para guardar el código en el sistema.
        OBLIGATORIO: Debes incluir el código fuente completo dentro del parámetro 'contenido' de la herramienta.
        """
        respuesta = programador_con_herramientas.invoke(prompt_codigo)

        # Ejecutamos la herramienta física en el disco duro
        if hasattr(respuesta, 'tool_calls') and respuesta.tool_calls:
            for llamada in respuesta.tool_calls:
                if llamada['name'] == 'crear_archivo':
                    resultado = crear_archivo.invoke(llamada['args'])
                    print(f"   {resultado}")
        else:
            print(f"   ⚠️ El modelo falló al usar la herramienta para {archivo.ruta_relativa}")

    return {"logs": ["Codificación finalizada."]}

# ════════════════════════════════════════════════════════════
# 6. ORQUESTACIÓN Y COMPILACIÓN
# ════════════════════════════════════════════════════════════
flujo = StateGraph(EstadoProyecto)
flujo.add_node("arquitecto", nodo_arquitecto)
flujo.add_node("programador", nodo_programador)

flujo.set_entry_point("arquitecto")
flujo.add_edge("arquitecto", "programador")
flujo.add_edge("programador", END)

agente_creador = flujo.compile()

# ════════════════════════════════════════════════════════════
# 7. EJECUCIÓN (TERMINAL)
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("==================================================")
    print("🚀 AGENTE AUTÓNOMO CREADOR DE PROYECTOS")
    print("==================================================")

    # Aquí escribes lo que quieres que te construya
    peticion_usuario = input("¿Qué sistema quieres construir?: ")

    inputs = {"peticion": peticion_usuario, "logs": []}
    agente_creador.invoke(inputs)

    print("\n==================================================")
    print(f"🎉 ¡Proyecto finalizado! Revisa la carpeta: {os.path.abspath(WORKSPACE)}")
    print("==================================================")