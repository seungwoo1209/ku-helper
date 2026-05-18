FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --no-dev --frozen || uv sync --no-dev

COPY app ./app

RUN useradd --create-home --shell /bin/bash bot
USER bot

CMD ["uv", "run", "python", "-m", "app.main"]
