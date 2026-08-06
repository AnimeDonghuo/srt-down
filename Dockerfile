# Use the official Microsoft Playwright Python base image matching our library version
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure start script is executable
RUN chmod +x start.sh

# Start command
CMD ["./start.sh"]
