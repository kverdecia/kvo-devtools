import asyncio
import sys
import json
from pathlib import Path

import rich.console
from invoke.tasks import task
import dotenv

from kvo.devtools.index import Index
from kvo.devtools.package import Package
from kvo.devtools.packageindexes import PackageIndex
from kvo.devtools.dependencies import install_dependencies as devtools_install_dependencies
from kvo.devtools.setuppackage import setup_package as devtools_setup_package
from kvo.devtools.packageversion import PackageVersion


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


def _find_package_index(name: str) -> PackageIndex:
    index = _load_index()
    package_index = index.find_package_index(name)
    if package_index is None:
        console.log(f"Package index '{name}' not found in the index.", style="bold red")
        sys.exit(1)
    console.log(f"Package index '{name}' found in the index.", style="bold green")
    return package_index


@task
def find_package(c, name: str):
    package = _find_package(name)
    console.print(package)
    return package


@task
def find_package_index(c, name: str):
    package_index = _find_package_index(name)
    console.print(package_index)
    return package_index


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
    package = _find_package(name)
    with c.cd(package.path):
        c.run(f"open .")


@task
def code_package(c, name: str):
    """
    Opens vscode from a package directory.
    """
    package = _find_package(name)
    with c.cd(package.path):
        c.run(f"code .")


@task
def download_package(c, name: str):
    """
    Downloads a package.
    """
    package = _find_package(name)
    asyncio.run(package.download())


@task(aliases=['install-deps'])
def install_dependencies(c, name: str, package_index: str | None = None):
    """
    Installs dependencies of a package.
    """
    package = _find_package(name)
    index = _find_package_index(package_index) if package_index else None
    asyncio.run(devtools_install_dependencies(package, index))


@task
def setup_package(c, name: str, package_index: str | None = None):
    """
    Downloads a package and installs its dependencies.
    """
    package = _find_package(name)
    index = _find_package_index(package_index) if package_index else None
    asyncio.run(devtools_setup_package(package, index))


@task
def publish_package(c, name: str):
    """
    Publishes a package to its package index.
    """
    package = _find_package(name)
    asyncio.run(package.publish())


@task
def show_version(c, name: str):
    """
    Shows the version of the devtools package.
    """
    package = _find_package(name)
    package_version = PackageVersion.from_package(package)
    result = asyncio.run(package_version.get_version())
    console.log(f"Package '{package.name}' version: {result}", style="bold green")
