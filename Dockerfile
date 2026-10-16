FROM python:3.14-slim
COPY --from=docker.io/astral/uv:latest /uv /uvx /bin/

WORKDIR /agent
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/agent/.venv/bin:$PATH"
CMD ["uvicorn","agent.main:app","--host","0.0.0.0","--port","6969"]