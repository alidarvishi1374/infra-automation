# ==========================
# Stage 1: Builder
# ==========================
FROM registry.docker.ir/python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==========================
# Stage 2: Runtime
# ==========================
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY main.py .

EXPOSE 5000

RUN useradd -m appuser
USER appuser

CMD ["python", "main.py"]