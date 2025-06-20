import os
import abc
import asyncio
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from .types import PackageTypes, console
from .errors import PublishError
from .packageindexes import PythonPackageIndex


class PackagePublisher(BaseModel, metaclass=abc.ABCMeta):
    package_dir: Path
    package_index: str | None

    @abc.abstractmethod
    async def publish(self) -> None:
        ...

    @staticmethod
    def from_package_type(package_type: PackageTypes) -> type['PackagePublisher']:
        config = {
            PackageTypes.PYTHON_UV: PythonUvPackagePublisher,
        }
        try:
            return config[package_type]
        except KeyError:
            raise PublishError(f"There is no package type publisher registered for package type {package_type}.")


class PythonUvPackagePublisher(PackagePublisher):
    """
    Represents Python dependencies for a package.
    This class should implement the logic to install Python dependencies.
    """
    python_package_index: PythonPackageIndex = Field(default_factory=lambda data: PythonPackageIndex(package_index=data['package_index']))

    async def build(self) -> None:
        console.log(f"Building python package in {self.package_dir}...")
        command = ['uv', 'build']
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
            raise PublishError(
                f"Error publishing python package in {self.package_index} package index: {stderr.decode('utf-8') if stderr else ''}"
            )
        console.log(f"Python package published successfully in {self.package_index} package index.", style="bold green")        


    async def publish(self) -> None:
        await self.build()
        console.log(f"Publishing python package in {self.package_dir}...")
        command = ['uv', 'publish']
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.package_dir,
            start_new_session=True,
            env=self.python_package_index.upload_env,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise PublishError(
                f"Error publishing python package in {self.package_index} package index: {stderr.decode('utf-8') if stderr else ''}"
            )
        console.log(f"Python package published successfully in {self.package_index} package index.", style="bold green")
