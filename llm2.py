from __future__ import annotations
from groq import Groq
from pydantic import BaseModel, ConfigDict
import os
from pathlib import Path
import json



class LLM:
    def __init__(self,api_key:str):
        try:
            self.client=Groq(api_key=api_key)

        except Exception as e:
            return f"{e}, please provide the correct api key"

    def send(self,prompt:str,system_instructions:str)->str:
        try:
            response=self.client.chat.completions.create(
                messages=[
                    {
                        "role":"system",
                        "content":system_instructions,
                    },
                    {
                        "role":"user",
                        "content":prompt,
                    }
                ],
                model="qwen/qwen3.8-27b",
                temperature=0,

            )

        except Exception as e:
            return f"{e} occured, please try again!" 
