# Project Goal

Build an AI agent that constructs knowledge graphs from text, then understands, processes, and reasons over the resulting dataset using knowledge graph concepts. Primary objective: **optimize LLM cost while matching the output quality of high-end AI applications.**

## Environment

- **OS:** Linux

## Setup

All packages are installed only after `uv` is set up and a project virtual environment is created.

```bash
uv init <project_name>
cd <project_name>
uv venv
source .venv/bin/activate
```

## Installed Packages

| Package | Purpose / Docs | Install Command |
|---|---|---|
| **uv** | [Astral uv install guide](https://docs.astral.sh/uv/getting-started/installation/) | `sudo snap install astral-uv --classic` |
| **openai** | [OpenAI Python SDK](https://github.com/openai/openai-python) | `uv add openai` |
| **langchain** | [LangChain install docs](https://docs.langchain.com/oss/python/langchain/install) | `uv add langchain` |
| **langchain-openai** | LangChain OpenAI integration | `uv add langchain-openai` |
| **chromaDB** | [ChromaDB overview](https://docs.trychroma.com/docs/overview/introduction) | `uv add chromaDB` |
| **networkx** | [NetworkX install docs](https://networkx.org/documentation/stable/install.html) | `uv add networkx` |
| **uvicorn** | [Uvicorn docs](https://uvicorn.dev/) | `uv add uvicorn` |

