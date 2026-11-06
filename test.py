# from agent import chunk
# from pathlib import Path
# from agent.kg_generator import KG_Generator as kg

# path = Path("/home/rohitchillara/agent/alice_ch6-8.txt")

# document = chunk.load_text(path=path)

# sample = kg(document)
# sample.create_graph()


# from agent import queries

# print(queries.REL_TYPES)

# text = "mad hatter"


# words = text.split(' ')
# words = [w+"~" for w in words]
# text = " ".join(words)

# print(text)

from agent import graph
from agent import queries

A = graph.Graph()
test = A.get(query=queries.ALL_PREDICATES)[0][0]["predicates"]
print(test)