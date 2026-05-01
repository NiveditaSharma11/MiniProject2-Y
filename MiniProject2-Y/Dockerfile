# Smart Energy Grid Load Forecasting System
# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy dependency list first (layer caching — only reinstalls if requirements change)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the Flask port
EXPOSE 5000

# Environment variables (overridden by .env or docker-compose)
ENV FLASK_DEBUG=false
ENV FLASK_APP=app.py

# Run the application
CMD ["python", "app.py"]
