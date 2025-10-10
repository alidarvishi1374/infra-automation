# ======================
# Stage 1 — Build Stage
# ======================
FROM python:3.10-slim AS builder

# Prevent Python from writing .pyc files and enable unbuffered mode
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependencies file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ======================
# Stage 2 — Runtime Stage
# ======================
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered mode
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.10 /usr/local/lib/python3.10

# Copy application source code
COPY . .

# Expose Flask default port
EXPOSE 5000

# Run the Flask app with Gunicorn (production-ready)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
