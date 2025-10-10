# Use a lightweight Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# Set working directory inside container
WORKDIR /app

# Copy only requirements first to leverage Docker caching
COPY requirements.txt .

# Install dependencies (no cache to keep image small)
RUN pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the rest of the app (excluding patterns from .dockerignore)
COPY s3-panel-web-ui .

# Expose Flask port
EXPOSE 5000

# Default command to run the app
CMD ["python", "app.py"]
