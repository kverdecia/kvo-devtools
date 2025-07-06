import abc
import importlib.metadata
import asyncio
import subprocess
from pathlib import Path

import rich.console
from pydantic import BaseModel, Field, HttpUrl

from .types import PackageTypes
from .errors import DependenciesError
from .packageindexes import PythonPackageIndex
from .package import Package


console = rich.console.Console()


class DependenciesInstaller(BaseModel, metaclass=abc.ABCMeta):
    package_dir: Path
    package_index: str | None

    @abc.abstractmethod
    async def install(self) -> None:
        ...

    def check_package_dir(self) -> None:
        """
        Checks if the package directory is a valid directory.
        Raises DependencyError if the package directory is not valid.
        """
        if not self.package_dir.is_dir():
            raise DependenciesError(f"Package directory {self.package_dir} is not a valid directory.")

    @property
    def package_index_url(self) -> HttpUrl | None:
        raise DependenciesError("Package index URL is not supported for this dependency installer.")


class NodeJsDependenciesInstaller(DependenciesInstaller):
    """
    Represents Node.js dependencies for a package.
    This class should implement the logic to install Node.js dependencies.
    """

    async def install(self) -> None:
        self.check_package_dir()
        console.log(f"Installing dependencies for nodejs package in {self.package_dir}...")
        command = ['npm', 'install']
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.package_dir,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise DependenciesError(
                f"Error installing Node.js dependencies in {self.package_dir}: {stderr.decode('utf-8') if stderr else ''}"
            )
        console.log(f"Node.js dependencies installed successfully in {self.package_dir}.", style="bold green")


class PythonUvDependenciesInstaller(DependenciesInstaller):
    """
    Represents Python dependencies for a package.
    This class should implement the logic to install Python dependencies.
    """

    python_package_index: PythonPackageIndex = Field(default_factory=lambda data: PythonPackageIndex(package_index=data['package_index']))


    @property
    def package_venv(self) -> Path:
        """
        Returns the path to the active virtual environment.
        This is typically the '.venv' directory in the package directory.
        """
        return self.package_dir / '.venv'

    async def create_venv(self) -> None:
        """
        Initializes a virtual environment in the package directory if it does not exist.
        Raises DependencyError if the virtual environment cannot be created.
        """
        self.check_package_dir()
        if self.package_venv.is_dir():
            console.log(f"Virtual environment already exists in {self.package_venv}. Skipping creation.", style="bold yellow")
            return       
        console.log(f"Creating virtual environment in {self.package_venv}...")
        command = ['uv', 'venv', str(self.package_venv)]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.package_dir,
            start_new_session=True,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise DependenciesError(
                f"Error installing Python dependencies in {self.package_dir}: {stderr.decode('utf-8') if stderr else ''}"
            )
        console.log(f"Python virtual environment created successfully in {self.package_venv}.", style="bold green")

    async def install(self) -> None:
        console.log(f"Installing dependencies for python package in {self.package_dir}...")
        self.check_package_dir()
        if not self.package_venv.exists():
            await self.create_venv()
        command = ['uv', 'sync']
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.package_dir,
            start_new_session=True,
            env=self.python_package_index.index_env,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise DependenciesError(
                f"Error installing Python dependencies in {self.package_dir}: {stderr.decode('utf-8') if stderr else ''}"
            )
        console.log(f"Python dependencies installed successfully in {self.package_dir}.", style="bold green")


async def install_dependencies(package: Package, package_index: str | None = None) -> None:
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
    if not issubclass(Installer, DependenciesInstaller):
        raise DependenciesError(f"The entry point '{entrypoint.name}' does not point to a valid DependenciesInstaller subclass.")
    console.log(f"Installing dependencies for package '{package.name}' of type '{package.type}' using entry point value '{entrypoint.value}'.")
    installer = Installer(package_dir=package.path, package_index=package_index or package.package_index)
    await installer.install()
