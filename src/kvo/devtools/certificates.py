import asyncio
from pathlib import Path
from collections.abc import Iterator

from pydantic import BaseModel, Field, field_validator, DirectoryPath, FilePath

from .types import console
from .package import Package
from .errors import CertificateCreationError


class Certificates(BaseModel):
    certificates_dir: DirectoryPath = Field(
        ..., description="Path to the directory containing certificate files."
    )
    ca_bundle_path: FilePath = Field(
        ..., description="Path to the CA bundle file. If relative, it is relative to certificates_dir."
    )

    @field_validator('ca_bundle_path', mode='before')
    @classmethod
    def validate_ca_bundle_path(cls, ca_bundle_path, info):
        """
        Validates and adjusts the ca_bundle_path to be absolute if it's relative.
        """
        ca_bundle_path = Path(ca_bundle_path)
        if ca_bundle_path.is_absolute():
            return str(ca_bundle_path)
        certificates_dir = info.data.get('certificates_dir')
        return str(Path(certificates_dir) / ca_bundle_path)

    @property
    def public_certificates(self) -> Iterator[Path]:
        """
        Yields all public certificate files in the certificates_dir.
        """
        certs_dir = Path(self.certificates_dir)
        for cert_file in certs_dir.glob('*.pem'):
            if str(cert_file).endswith('-key.pem'):
                continue
            yield cert_file

    def get_certificates_missing_in_bundle(self) -> list[Path]:
        content = self.ca_bundle_path.read_text()
        for certificate in self.public_certificates:
            cert_content = certificate.read_text()
            if cert_content not in content:
                yield certificate

    def add_certificates_to_bundle(self) -> None:
        """
        Adds all public certificates to the CA bundle file if they are not already present.
        """
        with self.ca_bundle_path.open('a') as bundle_file:
            for certificate in self.get_certificates_missing_in_bundle():
                cert_content = certificate.read_text()
                bundle_file.write(f"\n{cert_content}")

    async def create_package_certificates(self, package: Package) -> None:
        """
        Creates symbolic links for the public certificates in the package's parent directory.
        """
        if not package.dns:
            console.log(f"No DNS entries found for package '{package.name}'. Skipping certificate creation.", style="bold yellow")
            return
        with self.ca_bundle_path.open('a') as bundle_file:
            bundle_content = self.ca_bundle_path.read_text()
            for dns in package.dns:
                cert_path = self.certificates_dir / f"{dns}.pem"
                if cert_path.exists():
                    console.log(f"Certificate for DNS '{dns}' already exists. Skipping creation.", style="bold yellow")
                    continue
                command = ['mkcert', dns]
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.certificates_dir,
                )
                _, stderr = await process.communicate()
                if process.returncode != 0:
                    raise CertificateCreationError(
                        f"Error creating certificate for DNS '{dns}': {stderr.decode('utf-8') if stderr else ''}"
                    )
                console.log(f"Successfully created certificate for DNS '{dns}'.", style="bold green")
                cert_content = cert_path.read_text()
                if cert_content not in bundle_content:
                    bundle_file.write(f"\n{cert_content}")
                    console.log(f"Added certificate for DNS '{dns}' to CA bundle.", style="bold green")
