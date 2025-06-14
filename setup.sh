#!/bin/bash
# MaxMind GeoIP API Server - Developed by acidvegas in Python (https://git.acid.vegas/maxmind-server)
# maxmind-server/setup.sh

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Create necessary directories
mkdir -p assets
mkdir -p logs

# Copy service file
cp assets/maxmind.service /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable and restart service
systemctl enable maxmind && systemctl restart maxmind