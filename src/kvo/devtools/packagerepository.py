from datetime import datetime
from collections.abc import Sequence
from zoneinfo import ZoneInfo


import httpx
from tzlocal import get_localzone_name
import rich.console
from rich.table import Table
from pydantic import BaseModel, SecretStr
import git
import git.exc

from .errors import PackageRepositoryError
from .package import Package
from .index import Index


console = rich.console.Console()

local_tz_name = get_localzone_name()
local_tz = ZoneInfo(local_tz_name)


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
    pat_token: SecretStr | list[SecretStr] | None = None

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

    def get_active_branch_name(self) -> str:
        """
        Get the current branch of the package repository.
        If the package is not a git repository, it raises an error.
        """
        return self.get_active_branch().branch_name

    async def get_remote_branch(self, branch_name: str) -> PackageBranch | None:
        """
        Get a remote branch by its name.
        If the package is not a git repository, it raises an error.
        """
        if self.pat_token is None:
            raise PackageRepositoryError("Personal Access Token (PAT) is required to access remote branches.")
        async with httpx.AsyncClient() as client:
            try:
                url = f"https://api.github.com/repos/{self.package.repository.owner}/{self.package.repository.name}/branches/{branch_name}"

                tokens = self.pat_token if isinstance(self.pat_token, list) else [self.pat_token]
                for token in tokens:
                    headers = {"Authorization": f"token {token.get_secret_value()}"}
                    response = await client.get(url, headers=headers)
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    data = response.json()
                    commit_date_utc = datetime.fromisoformat(
                        data['commit']['commit']['committer']['date'].replace('Z', '+00:00')
                    )
                    commit_date_local = commit_date_utc.astimezone(local_tz)
                    return PackageBranch(
                        package_name=self.package.name,
                        branch_name=data['name'],
                        commit=data['commit']['sha'],
                        date=commit_date_local
                    )
            except httpx.HTTPStatusError as e:
                console.log(f"Error fetching remote branch '{branch_name}': {e}", style="bold red")
                raise
        return None

    async def get_remote_active_branch(self) -> PackageBranch | None:
        """
        Get the remote active branch of the package repository.
        If the package is not a git repository, it raises an error.
        """
        active_branch_name = self.get_active_branch_name()
        return await self.get_remote_branch(active_branch_name)
    
    def is_dirty(self) -> bool:
        """
        Check if the package repository is dirty.
        A repository is considered dirty if it has uncommitted changes.
        """
        repository = self.get_local_git_repo()
        return repository.is_dirty()

    @classmethod
    def from_package(cls, package: Package, pat_token: SecretStr | list[SecretStr] | None = None) -> 'PackageRepository':
        return cls(package=package, pat_token=pat_token)

    @staticmethod
    async def list_active_branches(index: Index, pat_token: SecretStr | list[SecretStr]) -> list[PackageBranchWithOrigin]:
        """
        List the active branches of all packages in the index.
        Returns a list of ActiveBranch objects.
        """
        active_branches = []
        for package in index.packages:
            repository = PackageRepository.from_package(package, pat_token)
            try:
                active_branch = repository.get_active_branch()
                origin_branch = await repository.get_remote_active_branch()
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
