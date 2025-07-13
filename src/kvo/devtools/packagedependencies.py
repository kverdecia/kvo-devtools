from typing import Any
import abc
import importlib.metadata
import os
import asyncio
import subprocess

import rich.console
from pydantic import BaseModel

from .errors import DependenciesError
from .packageindexes import PackageIndex
from .package import Package


console = rich.console.Console()


class PackageDependenciesInstaller(BaseModel, metaclass=abc.ABCMeta):
    package: Package
    package_index: PackageIndex | None = None

    @abc.abstractmethod
    async def install_dependencies(self) -> None:
        ...

    @classmethod
    def from_package(cls, package: Package, package_index: PackageIndex | None = None) -> 'PackageDependenciesInstaller':
        if package.type is None:
            raise ValueError("Package type is not set for this package.")
        entrypoints_group_name = 'kvo-devtools-dependencies-installer'
        entrypoints = importlib.metadata.entry_points(group=entrypoints_group_name)
        if not entrypoints:
            raise DependenciesError(f"No entry points found for group '{entrypoints_group_name}'. Ensure you have registered the dependencies installer for package type '{package.type}'.")
        entrypoint = next((ep for ep in entrypoints if ep.name == package.type.value), None)
        if entrypoint is None:
            raise DependenciesError(f"No entry point found for package type '{package.type}' in group '{entrypoints_group_name}'. Ensure you have registered the dependencies installer for this package type.")
        installer = entrypoint.load()
        if not issubclass(installer, cls):
            raise DependenciesError(f"The entry point '{entrypoint.name}' does not point to a valid DependenciesInstaller subclass.")
        return installer(package=package, package_index=package_index)


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
    async def install_dependencies(self) -> None:
        console.log(f"Installing Python dependencies of package '{self.package.name}'...")
        command = ['uv', 'sync']
        kwargs: dict[str, Any] = {}
        if self.package_index:
            env = dict(os.environ)
            env.pop('VIRTUAL_ENV', None)
            env['UV_INDEX'] = f'{self.package_index.name}={self.package_index.download_url}'
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
