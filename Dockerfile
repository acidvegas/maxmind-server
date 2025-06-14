# MaxMind GeoIP API Server - Developed by acidvegas in Python (https://git.acid.vegas/maxmind-server)
# maxmind-server/Dockerfile

FROM python:3.12-alpine

WORKDIR /app

# Copy entire repository
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the API server
CMD ["python", "main.py"] 