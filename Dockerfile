# 1. Use the official lightweight Python image
FROM python:3.10-slim

# 2. Prevent Python from buffering stdout/stderr (better for GCP logging)
ENV PYTHONUNBUFFERED=True

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Copy your requirements first to leverage Docker layer caching
COPY requirements.txt .

# 5. Install your dependencies, plus the functions-framework
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install functions-framework

# 6. Copy the rest of your project code into the container
COPY . .

# 7. Run the web service on container startup.
# NOTE: Ensure --target matches the exact name of your function in main.py
CMD ["functions-framework", "--target=drive_to_spotify", "--port=8080", "--host=0.0.0.0"]
