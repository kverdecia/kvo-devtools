import os
import asyncio
from pathlib import Path
import string

from pydantic import BaseModel, Field, AnyHttpUrl, ConfigDict

from . import gitservice
from .types import PackageTypes, AnyHttpUrlAdapter


class Repository(BaseModel):
    "Represents a github repository."
    url: AnyHttpUrl | str = Field(
        ..., description="The URL of the package repository."
    )
    branch: str | None = Field(
        None, description="The branch of the package repository to clone."
    )

    model_config = ConfigDict(extra='forbid')

    @staticmethod
    def split_repo_path(path: str) -> tuple[str, str]:
        try:
            owner, repo_name = path.split('/')
            if not repo_name.endswith('.git'):
                raise ValueError("GitHub repository URL must end with '.git'.")
            return owner, repo_name.replace('.git', '')
        except ValueError as error:
            raise ValueError("Invalid GitHub repository URL format.") from error

    def _parts(self) -> tuple[str, str]:
        """
        Returns the parts of the repository URL.
        This is used to extract the owner and repository name.
        """
        url = str(self.url)
        if str(url).startswith('git@github.com:'):
            repository = str(url).replace('git@github.com:', '', 1)
            return self.split_repo_path(repository)
        parsed_url = AnyHttpUrlAdapter.validate_python(self.url)
        if parsed_url.scheme in {'http', 'https'} and isinstance(parsed_url.path, str):
            return self.split_repo_path(parsed_url.path)
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


class Docker(BaseModel):
    container_name: str | None = Field(None, description="The name of the Docker container.")
    port: int | None = Field(8_000, description="The port to expose for the Docker container.")
    args: dict[str, str] | None = Field(
        None, description="The arguments to pass to the Docker build command. Keys are the argument names and values are the argument values. "
        " If you want to pass environment variables, you can use the format $ENV_<var_name> or ${ENV_<var_name>}, for example: ${ENV_NPM_TOKEN}. "
        " This format is the one used by the python string module template strings"
    )

    def template_context(self) -> dict[str, str]:
        """Returns the context to use in template substitutions.

        Returns:
            dict[str, str]: The template context.
        """
        result = {}
        for key, value in os.environ.items():
            result[f"ENV_{key}"] = value
        return result

    def get_args(self) -> dict[str, str]:
        """Returns the arguments to pass to the Docker build command. The values of the arguments will be resolved at runtime.

        Returns:
            dict[str, str]: The arguments to pass to the Docker build command.
        """
        params = self.args or {}
        result = {}
        for key, value in params.items():
            template = string.Template(value)
            result[key] = template.substitute(self.template_context())
        return result

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
    docker: Docker | None = Field(
        None,
        description="The Docker configuration for the package, if applicable."
    )
    dns: list[str] | None = Field(
        None,
        description="List of DNS names associated with the package, if applicable."
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
