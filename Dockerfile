# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the necessary ports
# TCP for clients, UDP for heartbeats/replication
EXPOSE 8000-8002

# The main command to run when the container starts
# The server_id will be passed in from docker-compose
CMD ["python", "-m", "server.main"] 