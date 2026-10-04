FROM python:3.11-slim

# Prevent Python from writing .pyc files & buffer stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=7860 \
    HOST=0.0.0.0 \
    DOWNLOADS_DIR=/app/downloads \
    MAX_FILE_AGE_SECONDS=1800 \
    RATE_LIMIT_PER_MINUTE=5 \
    ENABLE_YOUTUBE=false \
    ENVIRONMENT=production

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create downloads folder with write permissions for Hugging Face Spaces (user 1000)
RUN mkdir -p /app/downloads && chmod 777 /app/downloads

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Set permissions for non-root user execution in Hugging Face Spaces
RUN chmod -R 777 /app/downloads

# Expose Hugging Face Spaces port
EXPOSE 7860

# Start FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
