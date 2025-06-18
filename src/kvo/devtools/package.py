import asyncio
from pathlib import Path

from pydantic import BaseModel, Field, AnyHttpUrl, TypeAdapter


from . import gitservice


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

    def download_sync(self) -> None:
        """
        Clone the package repository to the specified path.
        This method should be implemented to perform the actual cloning operation.
        """
        repo = gitservice.RepositoryService(
            url=self.repository.url,
            branch=self.repository.branch,
            parent_dir=self.parent_dir
        )
        repo.clone()
        repo.checkout_branch()
        repo.pull()
    
    async def download_async(self) -> None:
        await asyncio.to_thread(self.download_sync)
