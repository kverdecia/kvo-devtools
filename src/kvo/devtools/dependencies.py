import abc
import importlib.metadata
import os
import asyncio
import subprocess
from pathlib import Path

import rich.console
from pydantic import BaseModel, Field, HttpUrl

from .types import PackageTypes
from .errors import DependenciesError
from .packageindexes import PythonPackageIndex, PackageIndex
from .package import Package


console = rich.console.Console()


class PackageDependenciesInstaller(BaseModel, metaclass=abc.ABCMeta):
    package: Package
    package_index: PackageIndex | None = None

    @abc.abstractmethod
    async def install_dependencies(self) -> None:
        ...


class NodeJsPackageDependenciesInstaller(PackageDependenciesInstaller):
    async def install_dependencies(self) -> None:
        console.log(f"Installing Node.js dependencies of package package '{self.package.name}'...")
        command = ['npm', 'install']
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.package.path,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise DependenciesError(
                f"Error installing Node.js package '{self.package.name}': {stderr.decode('utf-8') if stderr else ''}"
            )
        console.log(f"Node.js package '{self.package.name}' installed successfully.", style="bold green")


class UVPythonPackageDependenciesInstaller(PackageDependenciesInstaller):
    python_package_index: PythonPackageIndex = Field(default_factory=lambda: PythonPackageIndex(package_index=None))

    @property
    def package_venv(self) -> Path:
        return self.package.path / '.venv'

    async def create_venv(self) -> None:
        if self.package_venv.is_dir():
            console.log(f"Virtual environment already exists in {self.package_venv}. Skipping creation.", style="bold yellow")
            return
        console.log(f"Creating virtual environment in {self.package_venv}...")
        command = ['uv', 'venv', str(self.package_venv)]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.package.path,
            start_new_session=True,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise DependenciesError(
                f"Error creating virtual environment for package '{self.package.name}': {stderr.decode('utf-8') if stderr else ''}"
            )
        console.log(f"Virtual environment created successfully in {self.package_venv}.", style="bold green")

    async def install_dependencies(self) -> None:
        console.log(f"Installing Python dependencies of package '{self.package.name}'...")
        # if not self.package_venv.exists():
        #     await self.create_venv()
        command = ['uv', 'sync']
        kwargs = {}
        if self.package_index:
            env = dict(os.environ)
            env.pop('VIRTUAL_ENV', None)
            env['UV_INDEX']=f'{self.package_index.name}={self.package_index.download_url}'
            if self.package_index.insecure_host:
                env['UV_INSECURE_HOST'] = str(self.package_index.download_url.host)
            kwargs['env'] = env
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.package.path,
            start_new_session=True,
            **kwargs,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise DependenciesError(
                f"Error installing Python package '{self.package.name}': {stderr.decode('utf-8') if stderr else ''}"
            )
        console.log(f"Python package '{self.package.name}' installed successfully.", style="bold green")


async def install_dependencies(package: Package, package_index: PackageIndex | None = None) -> None:
    """
    Installs dependencies for a given package synchronously.
    This function is a wrapper around the package type dependency installer class.
    
    For each package type you want to support, there must be an entry point registered
    in the group `kvo-devtools-dependencies-installer` with the same name of the package
    type.
    
    :param package: The package for which to install dependencies.
    :param package_index: Optional package index URL to use for installation.
    """
    if package.type is None:
        raise ValueError("Package type is not set for this package.")
    entrypoints_group_name = 'kvo-devtools-dependencies-installer'
    entrypoints = importlib.metadata.entry_points(group=entrypoints_group_name)
    if not entrypoints:
        raise DependenciesError(f"No entry points found for group '{entrypoints_group_name}'. Ensure you have registered the dependency installer for package type '{package.type}'.")
    entrypoint = next((ep for ep in entrypoints if ep.name == package.type.value), None)
    if entrypoint is None:
        raise DependenciesError(f"No entry point found for package type '{package.type}' in group '{entrypoints_group_name}'. Ensure you have registered the dependency installer for this package type.")
    Installer = entrypoint.load()
    if not issubclass(Installer, PackageDependenciesInstaller):
        raise DependenciesError(f"The entry point '{entrypoint.name}' does not point to a valid DependenciesInstaller subclass.")
    console.log(f"Installing dependencies for package '{package.name}' of type '{package.type.value}' using entry point value '{entrypoint.value}'.")
    installer = Installer(package=package, package_index=package_index)
    await installer.install_dependencies()
