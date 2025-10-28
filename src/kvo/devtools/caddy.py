from pathlib import Path
import textwrap
import string

from pydantic import BaseModel, Field, field_validator, DirectoryPath, FilePath

from .dockercompose import DockerComposeService
from .package import Package
from .types import console


class Caddy(BaseModel):
    docker_compose: DockerComposeService
    caddy_file: FilePath
    sites_available_dir: DirectoryPath = Field(..., description="Directory for available Caddy site configurations. If relative, it's relative to the caddy file.")
    sites_enabled_dir: DirectoryPath = Field(..., description="Directory for enabled Caddy site configurations. If relative, it's relative to the caddy file.")

    @field_validator('sites_available_dir', 'sites_enabled_dir', mode='before')
    @classmethod
    def validate_site_dirs(cls, site_dir, info):
        """
        Validates and adjusts the site directories to be absolute if they're relative.
        """
        site_dir = Path(site_dir)
        if site_dir.is_absolute():
            return str(site_dir)
        caddy_file = info.data.get('caddy_file')
        return str(Path(caddy_file).parent / site_dir)

    async def restart_caddy(self):
        """
        Restarts the Caddy service using Docker Compose.
        """
        console.log(self)
        await self.docker_compose.restart()

    async def create_package_docker_site(self, package: Package, override: bool = False) -> None:
        """
        Creates a Caddy site configuration for the given package and enables it.
        """
        site_filename = self.sites_available_dir / package.name
        if site_filename.exists() and not override:
            console.log(
                f"Caddy site configuration for package '{package.name}' already exists at {site_filename}. Skipping creation.",
                style="yellow bold"
            )
            return
        if not package.dns:
            console.log(
                f"Package '{package.name}' does not have any DNS names configured. Cannot create Caddy site configuration.",
                style="red bold"
            )
            return
        template_str = """
        https://${dns} {
            tls /certs/${dns}.pem /certs/${dns}-key.pem

            reverse_proxy http://${container_name}:${port}
        }
        """
        template_str = textwrap.dedent(template_str).lstrip()
        template = string.Template(template_str)
        context = {
            "dns": package.dns[0],
            "container_name": package.docker.container_name if package.docker and package.docker.container_name else package.name,
            "port": package.docker.port if package.docker and package.docker.port else 8000,
        }
        site_config = template.substitute(context)
        site_filename.write_text(site_config)
