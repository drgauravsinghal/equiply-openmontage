FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ffmpeg chromium ca-certificates fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY studio_service/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
ENV PATH="/opt/venv/bin:$PATH" CHROME_PATH=/usr/bin/chromium PYTHONUNBUFFERED=1
COPY remotion-composer/package*.json ./remotion-composer/
RUN cd remotion-composer && npm ci --omit=dev
COPY . .
RUN mkdir -p projects/studio-runs && chown -R node:node /app
USER node
EXPOSE 10000
CMD ["python", "-m", "studio_service.server"]
