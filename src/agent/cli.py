import click
import agent.sample as s

@click.group()
def main()->None:
    st=0

main.add_command(s.create)