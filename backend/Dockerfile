FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN useradd -m app
WORKDIR /srv
# CPU-only torch: the GPU wheel would add ~2 GB and is never used
# PIP_INDEX_URL can point to a closer PyPI mirror when the default one is slow (build-time only)
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_DEFAULT_TIMEOUT=600 PIP_RETRIES=10
RUN --mount=type=cache,target=/root/.cache/pip pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install --index-url $PIP_INDEX_URL -r requirements.txt
# detector weights are baked into the image; at runtime the service never goes online
ENV MODELS_DIR=/srv/models
COPY app/ml/download_models.py /tmp/download_models.py
RUN python /tmp/download_models.py && rm /tmp/download_models.py
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY --from=frontend . ./frontend
ENV FRONTEND_DIR=/srv/frontend
RUN mkdir -p /srv/data && chown -R app /srv/data
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
