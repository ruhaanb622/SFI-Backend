FROM python:3.11

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y git && \
    pip install --no-cache-dir --upgrade pip

COPY . /app

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt

# Add WebSocket support
RUN pip install eventlet

# Expose the port used by your Flask-SocketIO server
EXPOSE 8500

ENV FLASK_ENV=production

# Use `eventlet` with `flask_socketio`
CMD ["python3", "socket_server.py"]
