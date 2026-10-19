from agent import chunk

path="/home/rohitchillara/agent/sample.txt"

chunks=chunk.chunking(path=path)

count=1
for chunk in chunks:
    print("###CHUNK "+str(count)+"###\n\n")
    print(chunk)
    count+=1