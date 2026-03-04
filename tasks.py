import os
import asyncio
import sys
import json
from pathlib import Path

import rich.console
from pydantic import SecretStr
from invoke.tasks import task
import dotenv

from kvo.devtools.index import IndexSettings
from kvo.devtools.package import Package
from kvo.devtools.packageindexes import PackageIndex
from kvo.devtools.packagedependencies import PackageDependenciesInstaller
from kvo.devtools.packageversion import PackageVersion
from kvo.devtools.cleanpackage import CleanPackage
from kvo.devtools.packagerepository import PackageRepository, PackageBranchWithOrigin
from kvo.devtools.setuppackage import setup_package as devtools_setup_package
from kvo.devtools.packagepublisher import PackagePublisher
from kvo.devtools.dockerbuilder import DockerBuilder
from kvo.devtools.dockercompose import DockerComposeService
from kvo.devtools import errors


dotenv.load_dotenv(override=True, verbose=True)
console = rich.console.Console()


def _load_index():
    """
    Loads the index.json file and returns an Index object.
    If the file does not exist, it raises a FileNotFoundError.
    """
    settings = IndexSettings.model_validate({})
    return settings.load_index()


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
def index_info(c):
    settings = IndexSettings.model_validate({})
    console.print(f"Index file: {settings.index_file.absolute()}")
    with settings.index_file.open() as f:
        index_data = json.load(f)
        schema_path = index_data.get('$schema', None)
        if schema_path:
            console.print(f"Index schema path: {Path(schema_path).absolute()}")
        else:
            console.print("No $schema field found in the index file.", style="bold yellow")
    console.print(f"Default index schema path: {settings.default_index_schema_path.absolute()}")



@task
def generate_index_schema(c, override: bool = False):
    """
    Generates the index schema of the index json file used by the devtools package.
    """
    try:
        settings = IndexSettings.model_validate({})
        settings.generate_index_schema(override=override)
        console.log(f"Index schema generated successfully in {settings.default_index_schema_path.absolute()}.", style="green")
    except FileExistsError:
        console.log(f"Schema file {settings.default_index_schema_path.absolute()} already exists. Use --override to overwrite it.", style="bold red")


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

@task
def create_package_certificates(c, name: str, override: bool = False):
    """
    Creates certificates for a package based on its DNS entries.
    """
    package = _find_package(name)
    index = _load_index()
    if index.certificates is None:
        console.log("No certificates configuration found in the index.", style="bold red")
        sys.exit(1)
    try:
        asyncio.run(index.certificates.create_package_certificates(package, override=override))
    except FileExistsError as e:
        console.log(f"{e} Use --override to overwrite existing certificates.", style="bold red")
        sys.exit(1)
    console.log(f"Certificates created successfully for package '{name}'.", style="bold green")


@task
def caddy_restart(c):
    """
    Restarts the Caddy server using Docker Compose.
    """
    index = _load_index()
    if index.caddy is None:
        console.log("No Caddy configuration found in the index.", style="bold red")
        sys.exit(1)
    asyncio.run(index.caddy.restart_caddy())
    console.log("Caddy server restarted successfully.", style="bold green")


@task
def caddy_open_sites_available(c):
    """
    Opens the Caddy sites-available directory.
    """
    index = _load_index()
    if index.caddy is None:
        console.log("No Caddy configuration found in the index.", style="bold red")
        sys.exit(1)
    with c.cd(index.caddy.sites_available_dir):
        c.run("open .")


@task
def caddy_open_sites_enabled(c):
    """
    Opens the Caddy sites-enabled directory.
    """
    index = _load_index()
    if index.caddy is None:
        console.log("No Caddy configuration found in the index.", style="bold red")
        sys.exit(1)
    with c.cd(index.caddy.sites_enabled_dir):
        c.run("open .")


@task
def caddy_docker_site(c, name: str):
    """
    Creates a Caddy site configuration for a package and enables it.
    """
    package = _find_package(name)
    index = _load_index()
    if index.caddy is None:
        console.log("No Caddy configuration found in the index.", style="bold red")
        sys.exit(1)
    try:
        index.caddy.docker_site_config(package).save(override=False)
        console.log(f"Caddy site configuration created successfully for package '{name}'.", style="bold green")
    except errors.DevToolsError as e:
        console.log(e, style="bold red")


@task
def caddy_devcontainer_site(c, name: str):
    """
    Creates a Caddy site configuration for a package based on its devcontainer and enables it.
    """
    package = _find_package(name)
    index = _load_index()
    if index.caddy is None:
        console.log("No Caddy configuration found in the index.", style="bold red")
        sys.exit(1)
    try:
        index.caddy.devcontainer_site_config(package).save(override=False)
        console.log(f"Caddy site configuration created successfully for package '{name}'.", style="bold green")
    except errors.DevToolsError as e:
        console.log(e, style="bold red")


@task
def compose_start(c, name: str):
    """
    Starts a Docker Compose service for a package.
    """
    package = _find_package(name)
    compose_service = DockerComposeService.from_package(package)
    asyncio.run(compose_service.start())

@task
def compose_stop(c, name: str):
    """
    Stops a Docker Compose service for a package.
    """
    package = _find_package(name)
    compose_service = DockerComposeService.from_package(package)
    asyncio.run(compose_service.stop())


@task
def compose_restart(c, name: str):
    """
    Restarts a Docker Compose service for a package.
    """
    package = _find_package(name)
    compose_service = DockerComposeService.from_package(package)
    asyncio.run(compose_service.restart())


@task
def compose_reset(c, name: str, show_logs: bool = False):
    """
    Restarts a Docker Compose service for a package.
    """
    compose_stop(c, name)
    compose_start(c, name)
    if show_logs:
        compose_logs(c, name, follow=True)


@task
def compose_logs(c, name: str, follow: bool = False):
    """
    Shows the logs of a Docker Compose service for a package.
    """
    package = _find_package(name)
    compose_service = DockerComposeService.from_package(package)
    asyncio.run(compose_service.logs(follow=follow))
