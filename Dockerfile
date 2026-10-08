# Data Delulu Control Plane Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source files
COPY app/ ./app/
COPY src/ ./src/
COPY data/ ./data/
COPY data_delulu_agent/ ./data_delulu_agent/
COPY .streamlit/ ./.streamlit/

# Create storage directory for tenant isolation metadata
RUN mkdir -p storage/tenants storage/synthetic

EXPOSE 8501

ENV PYTHONUNBUFFERED=1
ENV PORT=8501

CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
