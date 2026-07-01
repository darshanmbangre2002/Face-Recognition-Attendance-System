# Use official Python 3.11 slim base image
FROM python:3.11-slim

# Set environment variable defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set the application directory
WORKDIR /app

# Install operating system dependencies required for OpenCV, ONNX Runtime, and building C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements list
COPY requirements.txt .

# Install dependencies including gunicorn for production hosting
RUN pip install --no-cache-dir -r requirements.txt

# Pre-cache InsightFace model pack during the Docker build stage to enable instant startup on Render
RUN python -c "from insightface.app import FaceAnalysis; app = FaceAnalysis(name='buffalo_l'); app.prepare(ctx_id=-1)"

# Copy application files
COPY . .

# Create uploads directory structure inside image
RUN mkdir -p uploads/profiles uploads/attendance

# Expose default port
EXPOSE 10000

# Run Flask application with Gunicorn production server bound to Render's dynamic PORT
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --timeout 180 --workers 1 --threads 4 app:app"]
