# ---------- Stage 1: Build dependencies ----------
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ---------- Stage 2: Final runtime image ----------
FROM python:3.11-alpine

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

EXPOSE 5000
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

CMD ["python", "app.py"]
