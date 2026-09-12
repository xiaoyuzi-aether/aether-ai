FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY configs/ ./configs/

RUN pip install --no-cache-dir -e .

EXPOSE 8765

CMD ["uvicorn", "ether_ai.api:app", "--host", "0.0.0.0", "--port", "8765"]
