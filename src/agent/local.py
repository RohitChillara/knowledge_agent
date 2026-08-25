from ollama import chat
from ollama import ChatResponse

text='Rohit studies in University of Stuttgart. However, he also studied in GITAM University. He pursued his bachelors in ' \
    'GITAM when he was in India and is currently pursuing his masters in Stuttgart. Use this text and generate a RDF trip' \
    'le pattern for a knowledge graph.'
response: ChatResponse = chat(model='qwen3.8:latest', messages=[
  {
    'role': 'user',
    'content': text,
  },
])
print(response.message.content)