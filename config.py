#!/usr/bin/env python3
# MaxMind GeoIP API Server - Developed by acidvegas in Python (https://git.acid.vegas/maxmind-server)
# maxmind-server/config.py

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    raise ImportError('missing python-dotenv library (pip install python-dotenv)')


# Load environment variables
load_dotenv()

# MaxMind configuration (sensitive data from .env)
MAXMIND_LICENSE_KEY = os.getenv('MAXMIND_LICENSE_KEY')

# Server settings
HOST = os.getenv('MAXMIND_HOST', '127.0.0.1')
PORT = int(os.getenv('MAXMIND_PORT', '8000'))  # Convert to integer

# Paths
BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / 'assets/GeoLite2-City.mmdb'

# Update interval (in seconds)
UPDATE_INTERVAL = 86400 # 24 hours

# Create required directories
os.makedirs(BASE_DIR / 'assets', exist_ok=True) 