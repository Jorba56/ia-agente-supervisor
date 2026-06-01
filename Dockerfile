FROM python:3.11-slim
WORKDIR /app

# Instalamos la API
RUN pip install fastapi uvicorn requests pydantic

# Copiamos todos tus archivos (incluyendo el intocable agente_gemini.py)
COPY . .

# Exponemos el puerto de la web
EXPOSE 8000

# Arrancamos la API
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]