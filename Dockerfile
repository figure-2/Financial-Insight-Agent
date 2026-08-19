FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN useradd --create-home --uid 10001 fia \
    && install -d -o fia -g fia /app/src/fia_public

COPY --chown=fia:fia run.py /app/run.py
COPY --chown=fia:fia demo /app/demo
COPY --chown=fia:fia src/fia_public /app/src/fia_public

USER fia

EXPOSE 8765

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-I", "run.py", "smoke"]

CMD ["python", "-I", "run.py", "serve", "--port", "8765"]
