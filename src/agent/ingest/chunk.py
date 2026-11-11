from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from enum import Enum
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from pypdf import PdfReader
import os
from dotenv import load_dotenv
from typing import Literal
load_dotenv()


CHUNK_SIZE = 800
CHUNK_OVERLAP = 50  # keeps a fact from being split exactly at a chunk boundary
SUPPORTED = (".txt", ".pdf")

text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)

class chunking_types(Enum):
    Semantic="Semantic"
    Recursive="Recursive"


def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_pdf(path: Path) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def chunk_prose(text: str) -> list[str]:
    return text_splitter.split_text(text)



def chunking(document: str, chunking_type: Literal["Recursive", "Semantic"]) -> list[str]:
    kind = chunking_types(chunking_type)        # raises ValueError for unknown types

    if kind == chunking_types.Recursive:
        return chunk_prose(document)

    if kind == chunking_types.Semantic:
        embeddings = OpenAIEmbeddings(api_key=os.environ["OPENAI_API_KEY"],
                                      model="text-embedding-3-small")
        semantic_splitter = SemanticChunker(embeddings=embeddings,
                                            breakpoint_threshold_type="percentile",
                                            min_chunk_size=4000)
        return semantic_splitter.split_text(document)

    raise ValueError("Invalid Chunking Method. Supported: Recursive, Semantic")
