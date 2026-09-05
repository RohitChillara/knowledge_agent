from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
import csv

CHUNK_SIZE = 4000
CHUNK_OVERLAP = 200  # keeps a fact from being split exactly at a chunk boundary

text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)

def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def load_pdf(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def chunk_prose(text: str) -> list[str]:
    return text_splitter.split_text(text)

def chunk_csv(path: str, rows_per_chunk: int = 50) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    chunks = []
    for i in range(0, len(rows), rows_per_chunk):
        batch = rows[i : i + rows_per_chunk]
        # keep the header in every chunk so each one is self-describing
        chunk_text = ",".join(header) + "\n" + "\n".join(",".join(row) for row in batch)
        chunks.append(chunk_text)
    return chunks