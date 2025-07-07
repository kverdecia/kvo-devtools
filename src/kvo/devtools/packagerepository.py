from datetime import datetime
from collections.abc import Sequence

import rich.console
from rich.table import Table
from pydantic import BaseModel
import git
import git.exc

from .errors import PackageRepositoryError
from .package import Package
from .index import Index


console = rich.console.Console()


class PackageBranch(BaseModel):
    package_name: str
    branch_name: str
    commit: str
    date: datetime

    @staticmethod
    def print_table(branches: Sequence['PackageBranch']) -> None:
        """
        Print a table with the branches information.
        """
        table = Table()
        table.add_column("Package Name", style="bold green")
        table.add_column("Branch", style="blue")
        table.add_column("Commit", style="cyan")
        table.add_column("Date", style="cyan")

        for branch in branches:
            table.add_row(
                branch.package_name,
                branch.branch_name,
                branch.commit,
                branch.date.isoformat(),
            )

        console.print(table)


class PackageBranchWithOrigin(PackageBranch):
    origin_branch_name: str | None = None
    origin_commit: str | None = None
    origin_date: datetime | None = None

    @property
    def newest(self) -> str:
        """
        Returns which is the newest branch.
        If the origin date is None, it means that the branch is the newest.
        If the date of the branch is greater than the origin date, it means that the branch is newer than the origin branch.
        Otherwise, it means that the origin branch is newer.
        """
        if self.commit == self.origin_commit:
            return "Both"
        if self.origin_date is None:
            return "Local"
        if self.date > self.origin_date:
            return "Local"
        return "Origin"

    @staticmethod
    def print_table(branches: Sequence['PackageBranchWithOrigin']) -> None:
        """
        Print a table with the branches information.
        """
        table = Table()
        table.add_column("Package Name", style="bold green")
        table.add_column("Branch", style="blue")
        table.add_column("Commit", style="cyan")
        table.add_column("Date", style="cyan")
        table.add_column("Origin Commit", style="yellow", no_wrap=True)
        table.add_column("Origin Date", style="yellow", no_wrap=True)
        table.add_column("Newest", style="green", no_wrap=True)

        for branch in branches:
            newest_label = branch.newest
            if newest_label == "Local":
                newest_label = "[bold red]Local[/]"
            elif newest_label == "Origin":
                newest_label = "[bold red]Origin[/]"
            table.add_row(
                branch.package_name,
                branch.branch_name,
                branch.commit,
                branch.date.isoformat(),
                branch.origin_commit or "N/A",
                branch.origin_date.isoformat() if branch.origin_date else "N/A",
                newest_label
            )

        console.print(table)


class BranchesInfo(BaseModel):
    main: bool
    main_commit: str
    develop: bool
    develop_commit: str
    active_branch: str
    active_branch_commit: str


class PackageRepository(BaseModel):
    package: Package

    def get_local_git_repo(self) -> git.Repo:
        try:
            return git.Repo(self.package.path)
        except git.exc.InvalidGitRepositoryError:
            raise PackageRepositoryError(f"The path {self.package.path} is not a valid Git repository.")
        except git.exc.NoSuchPathError:
            raise PackageRepositoryError(f"The path {self.package.path} does not exist or is not a valid directory.")

    def get_active_branch(self) -> PackageBranch:
        """
        Get the active branch of the package repository.
        If the package is not a git repository, it raises an error.
        """
        repository = self.get_local_git_repo()
        active_branch = repository.active_branch
        return PackageBranch(
            package_name=self.package.name,
            branch_name=active_branch.name,
            commit=active_branch.commit.hexsha,
            date=active_branch.commit.committed_datetime,
        )
    
    def get_origin_branch(self) -> PackageBranch | None:
        """
        Get the origin branch of the package repository.
        If the package is not a git repository, it raises an error.
        """
        repository = self.get_local_git_repo()
        origin = repository.remote('origin')
        remote_branch_name = f"{origin.name}/{repository.active_branch.name}"
        
        found = (ref for ref in origin.refs if ref.name == remote_branch_name)
        remote_branch = next(found, None)
        if remote_branch is None:
            return None
        return PackageBranch(
            package_name=self.package.name,
            branch_name=remote_branch.name,
            commit=remote_branch.commit.hexsha,
            date=remote_branch.commit.committed_datetime,
        )

    def get_active_branch_name(self) -> str:
        """
        Get the current branch of the package repository.
        If the package is not a git repository, it raises an error.
        """
        return self.get_active_branch().branch_name

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

    @staticmethod
    def list_active_branches(index: Index) -> list[PackageBranchWithOrigin]:
        """
        List the active branches of all packages in the index.
        Returns a list of ActiveBranch objects.
        """
        active_branches = []
        for package in index.packages:
            repository = PackageRepository.from_package(package)
            try:
                active_branch = repository.get_active_branch()
                origin_branch = repository.get_origin_branch()
                branch = PackageBranchWithOrigin(
                    package_name=package.name,
                    branch_name=active_branch.branch_name,
                    commit=active_branch.commit,
                    date=active_branch.date,
                    origin_branch_name=origin_branch.branch_name if origin_branch else None,
                    origin_commit=origin_branch.commit if origin_branch else None,
                    origin_date=origin_branch.date if origin_branch else None
                )
                active_branches.append(branch)
            except PackageRepositoryError as e:
                console.log(f"Error with package '{package.name}': {e}", style="bold red")
        return active_branches
