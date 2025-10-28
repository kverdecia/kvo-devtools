class DevToolsError(Exception):
    """Base class for all devtools-related exceptions."""


class PackageIndexError(DevToolsError):
    """Exception raised for errors related to package indexes."""


class DependenciesError(DevToolsError):
    """Exception raised for errors related to dependencies."""


class PublishError(DevToolsError):
    """Exception raised for errors during the publishing process."""


class PackageRepositoryError(DevToolsError):
    """Exception raised for errors related to package repositories."""


class CertificateError(DevToolsError):
    """Exception raised for errors related to certificates."""


class DockerComposeError(DevToolsError):
    """Exception raised for errors related to Docker Compose operations."""


class CertificateCreationError(CertificateError):
    """Exception raised for errors during certificate creation."""


class CaddyError(DevToolsError):
    """Exception raised for errors related to Caddy server operations."""
