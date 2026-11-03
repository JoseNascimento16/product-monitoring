FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
CMD ["python", "-u", "app.py"]
