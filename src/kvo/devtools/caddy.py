from pydantic import BaseModel

from .dockercompose import DockerComposeService


class Caddy(BaseModel):
    docker_compose: DockerComposeService

    async def restart_caddy(self):
        """
        Restarts the Caddy service using Docker Compose.
        """
        await self.docker_compose.restart()
