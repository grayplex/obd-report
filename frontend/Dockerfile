FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

ENV PYTHONPATH=/app

EXPOSE 8501

CMD ["python", "app/main.py"]
