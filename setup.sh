#!/bin/bash
# MaxMind GeoIP API Server - Developed by acidvegas in Python (https://git.acid.vegas/maxmind-server)
# maxmind-server/setup.sh

# Load environment variables
[ -f .env ] && source .env || { echo "Error: .env file not found"; exit 1; }

# Set xtrace, exit on error, & verbose mode (after loading environment variables)
set -xev

# Create the container storage directory
mkdir -p /opt/container-storage/maxmind

# Remove existing docker container if it exists
docker rm -f maxmind-server 2>/dev/null || true

# Build the Docker image
docker build -t maxmind-server .

# Run the Docker container
docker run -d --name maxmind-server --restart unless-stopped -v /opt/container-storage/maxmind:/app/assets -p 127.0.0.1:8000:8000 -e MAXMIND_LICENSE_KEY=${MAXMIND_LICENSE_KEY} maxmind-server