import rich.console
from pydantic import BaseModel
import git
import git.exc

from .errors import PackageRepositoryError
from .package import Package


console = rich.console.Console()


class PackageRepository(BaseModel):
    package: Package

    def get_local_git_repo(self) -> git.Repo:
        try:
            return git.Repo(self.package.path)
        except git.exc.InvalidGitRepositoryError:
            raise PackageRepositoryError(f"The path {self.package.path} is not a valid Git repository.")
        except git.exc.NoSuchPathError:
            raise PackageRepositoryError(f"The path {self.package.path} does not exist or is not a valid directory.")

    def get_current_branch(self) -> str:
        """
        Get the current branch of the package repository.
        If the package is not a git repository, it raises an error.
        """
        repository = self.get_local_git_repo()
        return repository.active_branch.name

    def is_dirty(self) -> bool:
        """
        Check if the package repository is dirty.
        A repository is considered dirty if it has uncommitted changes.
        """
        repository = self.get_local_git_repo()
        return repository.is_dirty()

    @classmethod
    def from_package(cls, package: Package) -> 'PackageRepository':
        return cls(package=package)
