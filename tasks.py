import sys
import json
from pathlib import Path

import rich.console
from invoke.tasks import task

from kvo.devtools.index import Index


console = rich.console.Console()


def _load_index():
    """
    Loads the index.json file and returns an Index object.
    If the file does not exist, it raises a FileNotFoundError.
    """
    path = Path('index.json')
    if not path.exists():
        raise FileNotFoundError(f"Index file {path} does not exist.")
    
    with open(path, 'r') as stream:
        data = json.load(stream)
    
    return Index.model_validate(data)


@task
def generate_index_schema(c):
    """
    Generates the index schema for the devtools package.
    This task reads the index.json file and generates a Pydantic model schema.
    """
    schema = Index.model_json_schema()
    path = Path('index-schema.json')
    with open(path, 'w') as stream:
        json.dump(schema, stream, indent=4)
    console.log(f"Index schema generated successfully in {path}.", style="bold green")


@task
def download_package(c, name: str):
    """
    Downloads a package by its name from the index.
    If the package is not found, it raises a ValueError.
    """
    index = _load_index()
    package = index.find_package(name)
    if package is None:
        console.log(f"Package '{name}' not found in the index.", style="bold red")
        sys.exit(1)
    assert package is not None
    package.download_sync()
