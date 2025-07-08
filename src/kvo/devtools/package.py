import asyncio
from pathlib import Path

from pydantic import BaseModel, Field, AnyHttpUrl, ConfigDict

from . import gitservice
from .types import PackageTypes
from .publisher import PackagePublisher


class Repository(BaseModel):
    "Represents a github repository."
    url: AnyHttpUrl | str = Field(
        ..., description="The URL of the package repository."
    )
    branch: str | None = Field(
        None, description="The branch of the package repository to clone."
    )

    model_config = ConfigDict(extra='forbid')

    def _parts(self) -> tuple[str, str]:
        """
        Returns the parts of the repository URL.
        This is used to extract the owner and repository name.
        """
        url = str(self.url)
        if str(url).startswith('git@github.com:'):
            repository = str(url).replace('git@github.com:', '', 1)
            parts = repository.split('/')
            if len(parts) != 2:
                raise ValueError("Invalid GitHub repository URL format.")
            if not parts[1].endswith('.git'):
                raise ValueError("GitHub repository URL must end with '.git'.")
            return parts[0], parts[1].replace('.git', '')
        url = AnyHttpUrl(self.url)
        if url.scheme in ('http', 'https') and isinstance(url.path, str):
            parts = url.path.split('/')
            if len(parts) != 2:
                raise ValueError("Invalid GitHub repository URL format.")
            if not parts[1].endswith('.git'):
                raise ValueError("GitHub repository URL must end with '.git'.")
            return parts[0], parts[1].replace('.git', '')
        raise ValueError("Invalid GitHub repository URL format.")

    @property
    def owner(self) -> str:
        """
        Returns the owner of the repository.
        This is extracted from the URL, assuming a standard format.
        """
        owner, _ = self._parts()
        return owner

    @property
    def name(self) -> str:
        """
        Returns the name of the repository.
        This is extracted from the URL, assuming a standard format.
        """
        _, name = self._parts()
        return name


class Package(BaseModel):
    """
    Represents a package with a name and path.
    """
    name: str = Field(..., description="The name of the package.")
    repository: Repository = Field(
        ..., description="The repository information for the package."
    )
    parent_dir: Path = Field(
        ..., description="The path where to clone to the package repository."
    )
    type: PackageTypes | None = Field(
        None,
        description="The type of dependencies for the package, if applicable."
    )
    package_index: str | None = Field(
        None,
        description="The package index where this package is registered, if applicable."
    )

    model_config = ConfigDict(extra='forbid')

    def get_repository_service(self) -> gitservice.RepositoryService:
        """
        Returns a RepositoryService instance for the package repository.
        This service is used to interact with the Git repository.
        """
        return gitservice.RepositoryService(
            url=self.repository.url,
            branch=self.repository.branch,
            parent_dir=self.parent_dir
        )

    @property
    def path(self) -> Path:
        """
        Returns the full path to the package repository.
        This is constructed from the parent directory and the repository name.
        """
        return self.get_repository_service().local_path

    def download_sync(self) -> None:
        """
        Clone the package repository to the specified path.
        This method should be implemented to perform the actual cloning operation.
        """
        repo = self.get_repository_service()
        repo.clone()
        repo.checkout_branch()
        repo.pull()
    
    async def download(self) -> None:
        await asyncio.to_thread(self.download_sync)

    async def publish(self) -> None:
        """
        Publishes the package to its package index.
        This method should be implemented to perform the actual publishing operation.
        """
        if self.type is None:
            raise ValueError("Package type is not set for this package.")

        publisher_class = PackagePublisher.from_package_type(self.type)
        publisher = publisher_class(package_dir=self.path, package_index=self.package_index)
        await publisher.publish()
