# Base runtime image
FROM harbor.local/python/python:3.12-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Enable real-time stdout/stderr logs
ENV PYTHONUNBUFFERED=1

# Application working directory
WORKDIR /app

# Create non-root application user
RUN useradd --create-home --shell /bin/bash jira

# Copy application source code
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Set proper ownership for application files
RUN chown -R jira:jira /app

# Switch to non-root user
USER jira

# Application listens on port 5000
EXPOSE 5000

# Start application
CMD ["python", "main.py"]
