# 1. Use the latest stable Python 3.14 lightweight image
FROM python:3.14-slim

# 2. Ensure logs are sent straight to GCP Cloud Logging without buffering
ENV PYTHONUNBUFFERED=True

# 3. Set the working directory for your application
WORKDIR /app

# 4. Copy and install dependencies first (optimizes Docker build time)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install functions-framework

# 5. Copy the refactored main.py and any other project files
COPY . .

# 6. Start the Functions Framework on port 8080
# This makes your container compatible with Cloud Run's requirements
CMD ["functions-framework", "--target=drive_to_spotify", "--port=8080", "--host=0.0.0.0"]
