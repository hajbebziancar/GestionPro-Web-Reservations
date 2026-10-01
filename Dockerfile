FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends chromium fonts-dejavu-core fonts-noto-core && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8000 HBZ_CHROMIUM_PATH=/usr/bin/chromium
EXPOSE 8000
CMD ["python", "production_server.py"]
