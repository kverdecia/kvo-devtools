import abc
import importlib.metadata
import asyncio
import subprocess
import shutil

import rich.console
from pydantic import BaseModel

from .package import Package


console = rich.console.Console()


class CleanPackage(BaseModel, metaclass=abc.ABCMeta):
    package: Package

    @abc.abstractmethod
    async def clean_package(self) -> None:
        ...

    @classmethod
    def from_package(cls, package: Package) -> 'CleanPackage':
        if package.type is None:
            raise ValueError("Package type is not set for this package.")
        entrypoints_group_name = 'kvo-devtools-clean-package'
        entrypoints = importlib.metadata.entry_points(group=entrypoints_group_name)
        if not entrypoints:
            raise ValueError(f"No entry points found for group '{entrypoints_group_name}'. Ensure you have registered the package version retriever for package type '{package.type}'.")
        entrypoint = next((ep for ep in entrypoints if ep.name == package.type.value), None)
        if entrypoint is None:
            raise ValueError(f"No entry point found for package type '{package.type}' in group '{entrypoints_group_name}'. Ensure you have registered the package cleaner for package type '{package.type}'.")
        Processor = entrypoint.load()
        if not issubclass(Processor, cls):
            raise ValueError(f"The entry point '{entrypoint.name}' does not point to a valid CleanPackage subclass.")
        return Processor(package=package)


class NodeJsCleanPackage(CleanPackage):
    async def clean_package(self) -> None:
        package_json_path = self.package.path / 'package.json'
        if not package_json_path.is_file():
            raise FileNotFoundError(f"package.json not found in {self.package.path}")
        dist_dir = self.package.path / 'dist'
        if dist_dir.is_dir():
            shutil.rmtree(dist_dir)


class UvPythonCleanPackage(CleanPackage):
    async def call_clean_task(self) -> bool:
        tasks_path = self.package.path / 'tasks.py'
        if not tasks_path.is_file():
            return False
        command = ['uv', 'run', '-q', 'inv', 'clean']
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.package.path,
            start_new_session=True,
        )
        stdout, stderr = await process.communicate()
        error_message = stderr.decode('utf-8') if stderr else ''
        if process.returncode == 1 and error_message.strip() == "No idea what 'clean' is!":
            console.log(f"No 'clean' task found in {self.package.path / 'tasks.py'}", style='bold yellow')
            return False
        if process.returncode != 0:
            raise RuntimeError(f"Error executing 'clean' task in {self.package.path}: {error_message.strip()}")
        console.log(f"'clean' task executed successfully in {self.package.path}", style='bold green')
        return True

    async def clean_package(self) -> None:
        pyproject_path = self.package.path / 'pyproject.toml'
        if not pyproject_path.is_file():
            raise FileNotFoundError(f"pyproject.toml not found in {self.package.path}")
        task_executed = await self.call_clean_task()
        if task_executed:
            return
        dist_dir = self.package.path / 'dist'
        if dist_dir.is_dir():
            shutil.rmtree(dist_dir)
