# Start from Python 3.12 slim (Debian Trixie)
FROM python:3.12-slim-trixie

# Install curl and certificates
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Download and install uv (Python package installer)
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Add uv to PATH
ENV PATH="/root/.local/bin/:$PATH"

# Set working directory
WORKDIR /app

# Copy server file
COPY docker_server.py .

RUN mkdir -p /app/server

RUN uv venv
# Install dependencies
RUN uv pip install fastapi \
    uvicorn \
    ollama \
    psycopg2-binary \
    python-multipart \
    requests \
    python-dotenv

# Expose default FastAPI port
EXPOSE 1234

# Run the FastAPI app
CMD ["uv","run","docker_server.py"]
