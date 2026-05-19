FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

RUN useradd --create-home --shell /bin/bash bot

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --no-dev --frozen || uv sync --no-dev

RUN /app/.venv/bin/playwright install --with-deps chromium

COPY --chown=bot:bot app ./app

USER bot

CMD ["uv", "run", "--no-dev", "python", "-m", "app.main"]
