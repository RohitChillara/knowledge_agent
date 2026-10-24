from agent import chunk
from pathlib import Path
from agent.kg_generator import KG_Generator as kg

path = Path("/home/rohitchillara/agent/vw_emissions_excerpt.txt")

document = chunk.load_text(path=path)

sample = kg(document)


