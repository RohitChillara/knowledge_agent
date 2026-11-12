from __future__ import annotations
from typing import Callable, Optional
from pydantic import BaseModel, ValidationError
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv
from pathlib import Path
import asyncio
import hashlib
import json
load_dotenv()

MAX_RETRIES = 2          # 1 first attempt + 2 retries = 3 attempts
TEMP_STEP = 0.3          # temperature added on every retry
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = Path(os.environ.get("AGENT_CACHE_DIR", PROJECT_ROOT / "cache"))

# "provider:model", e.g. "openai:gpt-4.1-mini" or "groq:openai/gpt-oss-20b".
# The API key is read by the provider class itself (OPENAI_API_KEY, GROQ_API_KEY).
MODEL = os.environ["LLM_MODEL"]



class LLM:
    def __init__(self):
        # one chat model per (model, temperature), built on first use and reused
        self._models: dict[tuple[str, float], object] = {}

    def _model(self, model: str, temp: float):
        key = (model, temp)
        if key not in self._models:
            provider = model.split(":", 1)[0]
            self._models[key] = init_chat_model(model, temperature=temp, max_retries=3)
        return self._models[key]

    @staticmethod
    def _cache_key(model, system, prompt, schema_name, temp, schema_model) -> str:
        raw = "\x00".join([model, system, prompt, schema_name, str(temp), schema_model])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def send[T: BaseModel](self, prompt: str, system_instructions: str, schema: type[T],
                                 is_valid: Optional[Callable[[T], bool]] = None,
                                 attempt: int = 0, model: str = MODEL) -> T:
        temp = attempt * TEMP_STEP
        key = self._cache_key(model, system_instructions, prompt, schema.__name__, temp,
                              json.dumps(schema.model_json_schema(), sort_keys=True))
        path = CACHE_DIR / f"{key}.json"

        try:
            if path.exists():
                result = schema.model_validate_json(path.read_text(encoding="utf-8"))
            else:
                print(f"Attempt {attempt}, temperature {temp}, model {model}")
                extractor = self._model(model, temp).with_structured_output(
                    schema, method="json_schema", include_raw=True)
                out = await extractor.ainvoke([SystemMessage(system_instructions),
                                               HumanMessage(prompt)])

                finish = out["raw"].response_metadata.get("finish_reason")
                if finish == "length":
                    raise RuntimeError("output truncated (hit the token limit)")
                if out["parsing_error"] is not None or out["parsed"] is None:
                    raise RuntimeError(f"invalid structured output: {out['parsing_error']}")

                result = out["parsed"]

                # cache only responses that passed the checks
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                path.write_text(result.model_dump_json(), encoding="utf-8")

            # caller-defined check: retry with a higher temperature if it fails
            if is_valid is not None and not is_valid(result):
                if attempt < MAX_RETRIES:
                    return await self.send(prompt, system_instructions, schema,
                                           is_valid=is_valid, attempt=attempt + 1, model=model)
                print(f"WARNING: invalid after {attempt + 1} attempts: {prompt[:60]!r}")

            return result

        except ValidationError as e:
            raise RuntimeError(f"Invalid structure returned: {e}") from e

        except RuntimeError:
            raise

        except Exception as e:
            # error classes differ per provider (openai.RateLimitError, groq.RateLimitError, ...),
            # so rate limits are recognised by name to keep this provider-neutral
            if "RateLimit" in type(e).__name__ and attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** (attempt + 1))      # 2 s, then 4 s
                return await self.send(prompt, system_instructions, schema,
                                       is_valid=is_valid, attempt=attempt + 1, model=model)
            raise RuntimeError(f"LLM call failed ({type(e).__name__}): {e}") from e
