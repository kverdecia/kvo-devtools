from pathlib import Path
from collections.abc import Iterator

from pydantic import BaseModel, Field, field_validator, DirectoryPath, FilePath


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
