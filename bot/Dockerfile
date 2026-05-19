FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN pip install --no-cache-dir uv

RUN useradd --create-home --shell /bin/bash bot

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen || uv sync --no-dev

RUN /app/.venv/bin/playwright install --with-deps chromium \
    && chown -R bot:bot /ms-playwright

COPY --chown=bot:bot app ./app

USER bot

CMD ["/app/.venv/bin/python", "-m", "app.main"]
