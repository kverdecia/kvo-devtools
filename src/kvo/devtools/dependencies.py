from typing import Protocol
import os
import abc
import asyncio
import subprocess
from pathlib import Path

import rich.console
from pydantic import BaseModel, Field, HttpUrl

from .types import PackageTypes
from .errors import DependenciesError
from .packageindexes import PythonPackageIndex


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

    @staticmethod
    def from_package_type(package_type: PackageTypes) -> type['DependenciesInstaller']:
        config = {
            PackageTypes.PYTHON_UV: PythonUvDependenciesInstaller,
            PackageTypes.NODEJS: NodeJsDependenciesInstaller,
        }
        try:
            return config[package_type]
        except KeyError:
            raise DependenciesError(f"There is no dependency installer registered for package type {package_type}.")


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