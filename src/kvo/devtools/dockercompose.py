import asyncio
from pathlib import Path

from pydantic import BaseModel, field_validator, DirectoryPath

from .package import Package
from .types import console
from .errors import DockerComposeError


class DockerComposeService(BaseModel):
    service_name: str
    directory: DirectoryPath

    @field_validator('directory', mode='after')
    @classmethod
    def validate_directory(cls, directory, info):
        """
        Validates and adjusts the directory to be absolute if it's relative.
        """
        compose_file = Path(directory) / "docker-compose.yml"
        if not compose_file.exists():
            raise ValueError(f"Docker Compose file not found in directory: {directory}")
        return directory.resolve()

    async def start(self):
        """
        Starts docker compose service.
        """
        command = ['docker', 'compose', 'up', '-d', self.service_name]
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.directory,
        )
        await process.wait()
        if process.returncode != 0:
            raise DockerComposeError(f"Error starting docker compose service '{self.service_name}'.")
        console.log(f"Successfully started docker compose service '{self.service_name}'.", style="bold green")

    async def stop(self):
        """
        Stops docker compose service.
        """
        command = ['docker', 'compose', 'down', self.service_name]
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.directory,
        )
        await process.wait()
        if process.returncode != 0:
            raise DockerComposeError(f"Error stopping docker compose service '{self.service_name}'.")
        console.log(f"Successfully stopped docker compose service '{self.service_name}'.", style="bold green")

    async def restart(self):
        """
        Restarts docker compose service.
        """
        command = ['docker', 'compose', 'restart', self.service_name]
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.directory,
        )
        await process.wait()
        if process.returncode != 0:
            raise DockerComposeError(f"Error restarting docker compose service '{self.service_name}'.")
        console.log(f"Successfully restarted docker compose service '{self.service_name}'.", style="bold green")

    async def logs(self, follow: bool = True):
        """
        Shows logs for docker compose service.
        """
        command = ['docker', 'compose', 'logs']
        if follow:
            command.append('--follow')
        command.append(self.service_name)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.directory,
        )
        await process.wait()
        if process.returncode != 0:
            raise DockerComposeError(f"Error showing logs for docker compose service '{self.service_name}'.")
        console.log(f"Successfully showed logs for docker compose service '{self.service_name}'.", style="bold green")

    @staticmethod
    def from_package(package: Package) -> 'DockerComposeService':
        if package.type is None:
            raise ValueError("Package type is not set for this package.")
        if package.docker is None or package.docker.compose is None:
            raise ValueError("Docker compose configuration is not set for this package.")
        return DockerComposeService(
            service_name=package.docker.compose.service_name,
            directory=package.docker.compose.directory,
        )
