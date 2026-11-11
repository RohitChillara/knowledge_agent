from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def embed(text:str):
    response = client.embeddings.create(
        input = text,
        model = "text-embedding-3-small" 
    )
    return response.data[0].embedding