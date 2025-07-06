import asyncio
import sys
import json
from pathlib import Path

import rich.console
from invoke.tasks import task
import dotenv

from kvo.devtools.index import Index
from kvo.devtools.package import Package
from kvo.devtools.setuppackage import setup_package as devtools_setup_package


dotenv.load_dotenv(override=True, verbose=True)
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


def _find_package(name: str) -> Package:
    index = _load_index()
    package = index.find_package(name)
    if package is None:
        console.log(f"Package '{name}' not found in the index.", style="bold red")
        sys.exit(1)
    console.log(f"Package '{name}' found in the index.", style="bold green")
    return package


@task
def find_package(c, name: str):
    return _find_package(name)


@task
def generate_index_schema(c):
    """
    Generates the index schema of the index json file used by the devtools package.
    """
    schema = Index.model_json_schema()
    path = Path('index-schema.json')
    with open(path, 'w') as stream:
        json.dump(schema, stream, indent=4)
    console.log(f"Index schema generated successfully in {path}.", style="bold green")


@task
def open_package(c, name: str):
    """
    Opens a package directory.
    """
    package = find_package(c, name)
    with c.cd(package.path):
        c.run(f"open .")


@task
def code_package(c, name: str):
    """
    Opens vscode from a package directory.
    """
    package = find_package(c, name)
    with c.cd(package.path):
        c.run(f"code .")


@task
def download_package(c, name: str):
    """
    Downloads a package.
    """
    package = find_package(c, name)
    asyncio.run(package.download())


@task(aliases=['install-deps'])
def install_dependencies(c, name: str):
    """
    Installs dependencies of a package.
    """
    package = find_package(c, name)
    asyncio.run(package.install_deps())


@task
def setup_package(c, name: str):
    """
    Downloads a package and installs its dependencies.
    """
    package = _find_package(name)
    asyncio.run(devtools_setup_package(package))


@task
def publish_package(c, name: str):
    """
    Publishes a package to its package index.
    """
    package = find_package(c, name)
    asyncio.run(package.publish())
