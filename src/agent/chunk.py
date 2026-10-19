from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from enum import Enum
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
from pypdf import PdfReader


embeddings = HuggingFaceEmbeddings(
    model_name="Qwen/Qwen3-Embedding-0.6B",
    encode_kwargs={"normalize_embeddings": True},
)
CHUNK_SIZE = 4000
CHUNK_OVERLAP = 200  # keeps a fact from being split exactly at a chunk boundary
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



def chunking(path: Path, chunking_type : chunking_types=chunking_types.Semantic) -> list[str]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No such file: {path}")
    extension = path.suffix.lower()
    
    if extension == ".txt":
        text = load_text(path)
    elif extension == ".pdf":
        text = load_pdf(path)
    else:
        raise ValueError(
            f"Unsupported file type '{extension}'. Supported: {', '.join(SUPPORTED)}"
        )
    if not text.strip():
        raise ValueError(f"No text could be extracted from {path} (scanned PDF or empty file?)")

    

    if chunking_type==chunking_types.Recursive:
        return chunk_prose(text)
        
    else:
        semantic_splitter=SemanticChunker(embeddings=embeddings,breakpoint_threshold_type="percentile",min_chunk_size=4000)
        document=semantic_splitter.split_text(text)
        return document
