# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Better runtime behavior in containers
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PORT=8080

# Install security updates and minimal runtime deps
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (leverages Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Expose the port for local clarity (Cloud Run uses PORT env var)
EXPOSE 8080

# Use gunicorn; target the WSGI callable defined in app.py ("application")
CMD exec gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b :$PORT app:app