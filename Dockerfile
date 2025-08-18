FROM python:3.11-slim

WORKDIR /app

# Avoid creating .pyc files and ensure stdout/stderr are unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python dependencies first (better layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Default runtime configuration
ENV PORT=5000
ENV PATH_TO_SAVE=/data/saves
RUN mkdir -p /data/saves

EXPOSE 5000

# Launch the Flask app
CMD ["python", "app.py"]


