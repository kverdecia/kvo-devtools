import asyncio
from pathlib import Path

from pydantic import BaseModel, Field, AnyHttpUrl

from . import gitservice
from .dependencies import DependencyTypes


class Repository(BaseModel):
    url: AnyHttpUrl | str = Field(
        ..., description="The URL of the package repository."
    )
    branch: str | None = Field(
        None, description="The branch of the package repository to clone."
    )


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
    dependency_type: DependencyTypes | None = Field(
        None,
        description="The type of dependencies for the package, if applicable."
    )

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

    async def install_deps(self) -> None:
        """
        Installs dependencies for the package based on its dependency type.
        If the dependency type is not set, it raises a ValueError.
        """
        if self.dependency_type is None:
            raise ValueError("Dependency type is not set for this package.")
        
        installer_class = self.dependency_type.get_dependency_installer()
        installer = installer_class(package_dir=self.path)
        await installer.install()

    async def setup(self) -> None:
        """
        Sets up the package by downloading it and installing its dependencies.
        This method is an asynchronous wrapper for the download and install_deps methods.
        """
        await self.download()
        await self.install_deps()