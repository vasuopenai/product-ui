# Streamlit UI for the product API. Build context is this project's root.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ui ./ui
COPY examples ./examples
ENV API_URL=http://host.docker.internal:8000
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "ui/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
