FROM node:24-bookworm-slim AS youtube-js
FROM python:3.12-slim

# yt-dlp's bundled YouTube challenge solver needs a supported JS runtime.
COPY --from=youtube-js /usr/local/bin/node /usr/local/bin/node

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m nltk.downloader -d /usr/local/share/nltk_data averaged_perceptron_tagger_eng

COPY app.py ./
COPY grammar_course.py ./
COPY auth_support.py ./
COPY writing_coach ./writing_coach
COPY VERSION ./
COPY BECOMING_FRONTEND_VERSION ./
COPY compose.yaml ./
COPY docs/POSTGRES_FOUNDATION.md ./docs/POSTGRES_FOUNDATION.md
COPY docs/PERSISTENCE_RUNTIME_READINESS.md ./docs/PERSISTENCE_RUNTIME_READINESS.md
COPY docs/LEARNING_REPOSITORY_BOUNDARY.md ./docs/LEARNING_REPOSITORY_BOUNDARY.md
COPY docs/SPECIALIZED_PERSISTENCE_BOUNDARY.md ./docs/SPECIALIZED_PERSISTENCE_BOUNDARY.md
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY templates ./templates
COPY static ./static

RUN mkdir -p /data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
