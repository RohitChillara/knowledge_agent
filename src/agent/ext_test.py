from pathlib import Path
from agent import chunk

location = Path("/home/rohitchillara/agent/sample_students.pdf")

text=chunk.load_pdf(location)
chunks=chunk.chunk_prose(text)

count=1
for i in chunks:
    print(str(count)+"\n")
    count+=1
    print(i)
    print("\n")