# PlanArena demo on Hugging Face Spaces (Docker SDK).
# The code comes from GitHub, the city data from the Hugging Face dataset repo (built by
# `python -I -m planarena.tools.pack_demo`), and the web app is built here.
ARG REF=main
FROM node:22-slim AS web
ARG REF
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${REF} https://github.com/ParyaPayami/PlanArena /src
WORKDIR /src/web
RUN npm ci && npx vite build && rm -rf node_modules

FROM python:3.13-slim
ARG DATA_REPO=ParyaPayami/planarena-data
RUN useradd -m -u 1000 user
WORKDIR /app
COPY --from=web /src /app
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt huggingface_hub
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('${DATA_REPO}', repo_type='dataset', local_dir='/app')" \
 && rm -rf /app/.cache && chown -R user:user /app
USER user
ENV HOME=/home/user PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["python", "-m", "planarena.api", "--host", "0.0.0.0", "--port", "7860"]
