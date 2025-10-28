import os
import asyncio
import sys
import json
from pathlib import Path

import rich.console
from pydantic import SecretStr
from invoke.tasks import task
import dotenv

from kvo.devtools.index import Index
from kvo.devtools.package import Package
from kvo.devtools.packageindexes import PackageIndex
from kvo.devtools.packagedependencies import PackageDependenciesInstaller
from kvo.devtools.packageversion import PackageVersion
from kvo.devtools.cleanpackage import CleanPackage
from kvo.devtools.packagerepository import PackageRepository, PackageBranchWithOrigin
from kvo.devtools.setuppackage import setup_package as devtools_setup_package
from kvo.devtools.packagepublisher import PackagePublisher
from kvo.devtools.dockerbuilder import DockerBuilder


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

    return Index.model_validate_json(path.read_text())  # Validate the JSON structure


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
    path.write_text(json.dumps(schema, indent=4))
    console.log(f"Index schema generated successfully in {path}.", style="bold green")


@task
def open_package(c, name: str):
    """
    Opens a package directory.
    """
    package = _find_package(name)
    with c.cd(package.path):
        c.run("open .")


@task
def code_package(c, name: str):
    """
    Opens vscode from a package directory.
    """
    package = _find_package(name)
    with c.cd(package.path):
        c.run("code .")


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
    installer = PackageDependenciesInstaller.from_package(package, index)
    asyncio.run(installer.install_dependencies())


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
    publisher = PackagePublisher.from_package(package)
    asyncio.run(publisher.publish_package())


@task
def show_version(c, name: str):
    """
    Shows the version of the devtools package.
    """
    package = _find_package(name)
    package_version = PackageVersion.from_package(package)
    result = asyncio.run(package_version.get_version())
    console.log(f"Package '{package.name}' version: {result}", style="bold green")


@task
def clean_package(c, name: str):
    """
    Cleans a package by removing its distribution files.
    """
    package = _find_package(name)
    cleaner = CleanPackage.from_package(package)
    asyncio.run(cleaner.clean_package())
    console.log(f"Package '{package.name}' cleaned successfully.", style="bold green")


@task
def is_dirty(c, name: str):
    """
    Checks if a package repository is dirty (has uncommitted changes).
    """
    package = _find_package(name)
    repository = PackageRepository.from_package(package)
    if repository.is_dirty():
        console.log(f"Package '{package.name}' repository is dirty.", style="bold yellow")
    else:
        console.log(f"Package '{package.name}' repository is clean.", style="bold green")


@task
def list_dirty_packages(c):
    """
    Lists all packages that have dirty repositories (uncommitted changes).
    """
    index = _load_index()

    console.log("Checking for dirty packages...", style="bold blue")
    for package in index.packages:
        repository = PackageRepository.from_package(package)
        if repository.is_dirty():
            console.log(f"- '{package.name}'", style="bold yellow")


def get_github_token() -> list[SecretStr]:
    """
    Retrieves the GitHub personal access token from the environment variable.
    If the token is not set, it raises an error.
    """
    pat_token = [SecretStr(value) for value in os.environ.get('GITHUB_PERSONAL_ACCESS_TOKEN', '').split()]
    if not pat_token:
        console.log("GITHUB_PERSONAL_ACCESS_TOKEN environment variable is not set.", style="bold red")
        sys.exit(1)
    return pat_token


@task
def show_active_branches(c):
    """
    Shows the active branch of all packages in the index.
    """
    index = _load_index()
    branches = asyncio.run(PackageRepository.list_active_branches(index, get_github_token()))
    PackageBranchWithOrigin.print_table(branches)


@task
def package_branches(c, name: str):
    """
    Lists all branches of a package.
    """
    package = _find_package(name)
    repository = PackageRepository.from_package(package, get_github_token())
    branches = asyncio.run(repository.get_branches())
    PackageBranchWithOrigin.print_table(branches)


@task
def docker_build(c, name: str):
    """
    Builds a Docker image for a package.
    """
    package = _find_package(name)
    docker_builder = DockerBuilder.from_package(package)
    asyncio.run(docker_builder.build_image())


@task
def generate_ca_bundle(c):
    """
    Generates the CA bundle by adding missing certificates to the bundle file.
    """
    index = _load_index()
    if index.certificates is None:
        console.log("No certificates configuration found in the index.", style="bold red")
        sys.exit(1)
    index.certificates.add_certificates_to_bundle()
    console.log("CA bundle generated successfully.", style="bold green")