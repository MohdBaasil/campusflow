FROM python:3.12-slim

# Install system dependencies needed for compilation and OpenCV/InsightFace
# Force IPv4 to avoid network timeouts, and use libgl1 (replaces deprecated libgl1-mesa-glx)
RUN apt-get -o Acquire::ForceIPv4=true update && apt-get -o Acquire::ForceIPv4=true install -y --no-install-recommends \
    build-essential \
    cmake \
    gcc \
    g++ \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements file first to utilize Docker build cache
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port (Render sets $PORT dynamically, but documenting 5000 is standard)
EXPOSE 5000

# Start server using run.py
CMD ["python", "run.py"]
