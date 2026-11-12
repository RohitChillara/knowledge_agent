FROM python:3.14-slim
COPY --from=docker.io/astral/uv:latest /uv /uvx /bin/

WORKDIR /agent

# dependencies first, so code changes don't reinstall them
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# then the project itself (installs the `agent` command from [project.scripts])
COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/agent/.venv/bin:$PATH"

# LLM response cache and input documents live outside the image (mount them as volumes)
VOLUME ["/agent/cache", "/agent/data"]

# the CLI is the entry point: `docker run <image> ingest data/NIAM.txt --title NIAM`
ENTRYPOINT ["agent"]
CMD ["--help"]
