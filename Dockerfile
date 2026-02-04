# MaxMind GeoIP API Server - Developed by acidvegas in Python (https://git.acid.vegas/maxmind-server)
# maxmind-server/Dockerfile

# Base Python image
FROM python:3.12-alpine

# Create the assets directory
RUN mkdir -p /app/assets

# Set up in the application directory
WORKDIR /app

# Copy python requirements file
COPY requirements.txt .

# Set up Python environment and install dependencies
RUN python3 -m pip install --upgrade pip && python3 -m pip install --no-cache-dir --only-binary :all: -r requirements.txt --upgrade

# Cleanup the python requirements file (not needed at runtime)
RUN rm requirements.txt

# Copy the main application file
COPY main.py .

# Run the API server
CMD ["python", "main.py"] 