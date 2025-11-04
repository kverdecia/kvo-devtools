from pathlib import Path
import textwrap
import string

from pydantic import BaseModel, Field, field_validator, DirectoryPath, FilePath

from .dockercompose import DockerComposeService
from .package import Package
from .devcontainer import DevContainer
from . import errors


class CaddySiteConfig(BaseModel):
    package: Package
    sites_directory: DirectoryPath

    @property
    def site_filename(self) -> Path:
        return self.sites_directory / f'{self.package.name}.Caddyfile'

    @property
    def internal_address(self) -> str:
        return 'localhost'

    @property
    def port(self) -> int:
        return self.package.docker.port if self.package.docker and self.package.docker.port else 8000

    @property
    def dns(self) -> str:
        if not self.package.dns:
            raise errors.CaddyDnsMissingError(f"Package '{self.package.name}' does not have any DNS names configured.")
        return self.package.dns[0] if isinstance(self.package.dns[0], str) else self.package.dns[0].dns

    @property
    def https(self) -> bool:
        if not self.package.dns:
            raise errors.CaddyDnsMissingError(f"Package '{self.package.name}' does not have any DNS names configured.")
        if isinstance(self.package.dns[0], str):
            return True
        return self.package.dns[0].https

    @property
    def site_context(self) -> dict:
        return {
            "dns": self.dns,
            "internal_address": self.internal_address,
            "port": self.port,
        }

    def render_site_template(self, template: str) -> str:
        template_str = textwrap.dedent(template).lstrip()
        template = string.Template(template_str)
        return template.substitute(self.site_context)

    @property
    def https_site_content(self) -> str:
        template = """
        https://${dns} {
            tls /certs/${dns}.pem /certs/${dns}-key.pem

            reverse_proxy http://${internal_address}:${port}
        }
        """
        return self.render_site_template(template)

    @property
    def http_site_content(self) -> str:
        template = """
        http://${dns} {
            reverse_proxy http://${internal_address}:${port}
        }
        """
        return self.render_site_template(template)

    @property
    def site_content(self) -> str:
        if self.https:
            return self.https_site_content
        return self.http_site_content

    def save(self, override: bool = False) -> None:
        self.site_filename.write_text(self.site_content)


class DockerCaddySiteConfig(CaddySiteConfig):
    @property
    def internal_address(self) -> str:
        return self.package.docker.container_name if self.package.docker and self.package.docker.container_name else self.package.name


class DevcontainerCaddySiteConfig(CaddySiteConfig):
    @property
    def internal_address(self) -> str:
        devcontainer = DevContainer(package=self.package)
        return devcontainer.container_name or devcontainer.name


class Caddy(BaseModel):
    docker_compose: DockerComposeService
    caddy_file: FilePath
    sites_dir: DirectoryPath = Field(..., description="Directory for enabled Caddy site configurations. If relative, it's relative to the caddy file.")

    @field_validator('sites_dir', mode='before')
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
        await self.docker_compose.restart()

    @property
    def site_config(self) -> CaddySiteConfig:
        raise NotImplementedError("Use specific methods to create site configurations.")

    def docker_site_config(self, package: Package) -> CaddySiteConfig:
        return DockerCaddySiteConfig(
            package=package,
            sites_directory=self.sites_dir
        )

    def devcontainer_site_config(self, package: Package) -> CaddySiteConfig:
        return DevcontainerCaddySiteConfig(
            package=package,
            sites_directory=self.sites_dir
        )
