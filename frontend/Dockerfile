FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Streamlit configuration
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV PYTHONPATH=/app

CMD ["streamlit", "run", "app/main.py"]
