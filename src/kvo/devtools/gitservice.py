import asyncio
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import git
import git.exc
from rich.console import Console
from pydantic import BaseModel, Field, AnyHttpUrl


console = Console()


class GitError(Exception):
    ...


class RepositoryService(BaseModel):
    url: AnyHttpUrl | str = Field(..., description="The URL of the Git repository.")
    branch: str | None = Field(None, description="The branch of the repository to clone.")
    parent_dir: Path = Field(
        ..., description="The path where to clone the repository."
    )

    @property
    def local_name(self) -> str:
        """Extracts the repository name from the repository URL."""
        parsed_url = urlparse(str(self.url))
        if parsed_url.path:
            result = Path(parsed_url.path).name
            if result.endswith('.git'):
                return result[:-4]
            return result
        raise ValueError(f"Invalid repository URL: {self.url}: unable to extract name.")

    @property
    def local_path(self) -> Path:
        """Returns the full path to the repository."""
        return self.parent_dir / self.local_name

    def get_local_git_repo(self) -> git.Repo:
        try:
            return git.Repo(self.local_path)
        except git.exc.InvalidGitRepositoryError:
            raise GitError(f"The path {self.local_path} is not a valid Git repository.")
        except git.exc.NoSuchPathError:
            raise GitError(f"The path {self.local_path} does not exist or is not a valid directory.")

    def clone(self) -> None:
        """Clones the repository to the specified parent directory."""
        if self.local_path.exists():
            self.get_local_git_repo()
            console.log(f"Repository {self.local_path} already exists. Skipping clone.", style="bold yellow")
            return
        try:
            git.Repo.clone_from(str(self.url), self.local_path, branch=self.branch)
            console.log(f"Cloned repository {self.url} to {self.local_path}.", style="bold green")
        except git.exc.GitCommandError as e:
            raise GitError(f"Error cloning repository {self.url}: {str(e)}")
        
    def checkout_branch(self, branch: str | None = None) -> None:
        """Checks out the specified branch in the local repository."""
        branch = branch or self.branch
        repo = self.get_local_git_repo()
        try:
            repo.git.checkout(branch)
            console.log(f"Checked out branch {branch} in repository {self.url}.", style="bold green")
        except git.exc.GitCommandError as e:
            try:
                # If the branch does not exist, create it from the current HEAD
                repo.git.checkout('-b', branch)
                console.log(f"Created and checked out new branch {branch} in repository {self.url}.", style="bold green")
            except git.exc.GitCommandError as e:
                raise GitError(f"Error checking out branch {branch} in repository {self.url}: {str(e)}")

    def pull(self, branch: str | None = None) -> None:
        """Pulls the latest changes from the remote repository."""
        branch = branch or self.branch
        repo = self.get_local_git_repo()
        try:
            repo.remotes.origin.pull(branch)
            console.log(f"Pulled latest changes from branch {branch} in repository {self.url}.", style="bold green")
        except git.exc.GitCommandError as e:
            raise GitError(f"Error pulling from repository {self.url}: {str(e)}")
