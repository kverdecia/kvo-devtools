import asyncio
from pathlib import Path

from pydantic import BaseModel, field_validator, DirectoryPath

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
