import importlib.metadata
import json
import asyncio
import subprocess


from pydantic import BaseModel

from .package import Package
from .pythoninvoke import PythonInvoke


class DockerBuilder(BaseModel):
    package: Package

    async def get_build_args(self) -> list[str]:
        if self.package.docker is None:
            return []
        result = []
        for key, value in self.package.docker.get_args().items():
            result.append("--build-arg")
            result.append(f"{key}={value}")
        return result

    async def build_image(self) -> str | None:
        docker_file_path = self.package.path / 'Dockerfile'
        if not docker_file_path.is_file():
            raise FileNotFoundError(f"Dockerfile not found in {self.package.path}")
        command = [
            'docker', 'build',
            '--pull', '--rm', '--no-cache',
            *await self.get_build_args(),
            '-f', 'Dockerfile',
            '-t', f"{self.package.name}:latest",
            '.'
        ]
        process = await asyncio.create_subprocess_exec(
            *command,
            # stdout=subprocess.PIPE,
            # stderr=subprocess.PIPE,
            cwd=self.package.path,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise ValueError(
                f"Error building Docker image for package '{self.package.name}': {stderr.decode('utf-8') if stderr else ''}"
            )

    @staticmethod
    def from_package(package: Package) -> 'DockerBuilder':
        if package.type is None:
            raise ValueError("Package type is not set for this package.")
        entrypoints_group_name = 'kvo-devtools-docker-builder'
        entrypoints = importlib.metadata.entry_points(group=entrypoints_group_name)
        if not entrypoints:
            raise ValueError(f"No entry points found for group '{entrypoints_group_name}'. Ensure you have registered the docker builder for package type '{package.type}'.")
        entrypoint = next((ep for ep in entrypoints if ep.name == package.type.value), None)
        if entrypoint is None:
            raise ValueError(f"No entry point found for package type '{package.type}' in group '{entrypoints_group_name}'. Ensure you have registered the docker builder for package type '{package.type}'.")
        docker_builder = entrypoint.load()
        if not issubclass(docker_builder, DockerBuilder):
            raise ValueError(f"The entry point '{entrypoint.name}' does not point to a valid DockerBuilder subclass.")
        return docker_builder(package=package)


class NodeJsDockerBuilder(DockerBuilder):
    ...


class PythonUvDockerBuilder(DockerBuilder):
    async def build_image(self) -> str | None:
        python_invoke = PythonInvoke(package=self.package)
        tasks = await python_invoke.list_tasks()
        task_name = None
        if 'build-docker' in tasks:
            task_name = 'build-docker'
        elif 'docker-build' in tasks:
            task_name = 'docker-build'

        if task_name:
            await python_invoke.run_task(task_name)
        else:
            await super().build_image()
