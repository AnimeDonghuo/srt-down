# Use official lightweight Python 3.12 image
FROM python:3.12-slim

# Install system dependencies needed for Playwright and chromium compiling
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    wget \
    gnupg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and chromium browser dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application files
COPY . .

# Ensure start script is executable
RUN chmod +x start.sh

# Start command
CMD ["./start.sh"]
