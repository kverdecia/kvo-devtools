import abc
import asyncio
import subprocess
import importlib.metadata

from pydantic import BaseModel

from .types import console
from .errors import PublishError
from .package import Package


class PackagePublisher(BaseModel, metaclass=abc.ABCMeta):
    package: Package

    @abc.abstractmethod
    async def publish_package(self) -> None:
        ...

    @classmethod
    def from_package(cls, package: Package) -> 'PackagePublisher':
        if package.type is None:
            raise ValueError("Package type is not set for this package.")
        entrypoints_group_name = 'kvo-devtools-package-publisher'
        entrypoints = importlib.metadata.entry_points(group=entrypoints_group_name)
        if not entrypoints:
            raise PublishError(f"No entry points found for group '{entrypoints_group_name}'. Ensure you have registered the package publisher for package type '{package.type}'.")
        entrypoint = next((ep for ep in entrypoints if ep.name == package.type.value), None)
        if entrypoint is None:
            raise PublishError(f"No entry point found for package type '{package.type}' in group '{entrypoints_group_name}'. Ensure you have registered the package publisher for this package type.")
        publisher = entrypoint.load()
        if not issubclass(publisher, cls):
            raise PublishError(f"The entry point '{entrypoint.name}' does not point to a valid PackagePublisher subclass.")
        return publisher(package=package)


class PythonUvPackagePublisher(PackagePublisher):
    """
    Represents Python dependencies for a package.
    This class should implement the logic to install Python dependencies.
    """
    async def build(self) -> None:
        console.log(f"Building python package in {self.package.path}...")
        command = ['uv', 'build']
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.package.path,
            # start_new_session=True,
            # env=self.python_package_index.index_env,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise PublishError(
                f"Error building python package in {self.package.path}: {stderr.decode('utf-8') if stderr else ''}"
            )
        console.log(f"Successfully built python package in {self.package.path}.", style="bold green")

    async def publish_package(self) -> None:
        await self.build()
        console.log(f"Publishing python package in {self.package.path}...")
        command = ['uv', 'publish']
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.package.path,
            # start_new_session=True,
            # env=self.python_package_index.upload_env,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise PublishError(
                f"Error publishing python package in {self.package.path}: {stderr.decode('utf-8') if stderr else ''}"
            )
        console.log(f"Successfully published python package in {self.package.path}.", style="bold green")
