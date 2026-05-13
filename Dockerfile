# VM-style container for SimplePractice browser automation
# This container runs headless Chromium + Playwright to extract data from EMRs
# In production, this would run on a cloud VM (AWS EC2, GCP Compute, etc.)

FROM python:3.12-slim

# Install system dependencies for Playwright/Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (headless Chromium)
RUN playwright install chromium && playwright install-deps chromium

# Copy application code
COPY . .

# Expose the API port
EXPOSE 8000

# Run the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
