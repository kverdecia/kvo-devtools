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


class PackageBranchWithOrigin(BaseModel):
    package_name: str
    branch_name: str
    local_commit: str | None = None
    local_date: datetime | None = None
    remote_commit: str | None = None
    remote_date: datetime | None = None

    @property
    def newest(self) -> str:
        """
        Returns which is the newest branch.
        If the origin date is None, it means that the branch is the newest.
        If the date of the branch is greater than the origin date, it means that the branch is newer than the origin branch.
        Otherwise, it means that the origin branch is newer.
        """
        if self.local_commit == self.remote_commit:
            return "Both"
        if self.local_date is None:
            return "Remote"
        if self.remote_date is None:
            return "Local"
        if self.local_date > self.remote_date:
            return "Local"
        return "Remote"

    @staticmethod
    def print_table(branches: Sequence['PackageBranchWithOrigin']) -> None:
        """
        Print a table with the branches information.
        """
        table = Table()
        table.add_column("Package Name", style="bold green")
        table.add_column("Branch", style="blue")
        table.add_column("Local commit", style="cyan")
        table.add_column("Local date", style="cyan")
        table.add_column("Remote commit", style="yellow", no_wrap=True)
        table.add_column("Remote date", style="yellow", no_wrap=True)
        table.add_column("Newest", style="green", no_wrap=True)

        for branch in branches:
            newest_label = branch.newest if branch.newest == "Both" else f"[bold red]{branch.newest}[/]"
            table.add_row(
                branch.package_name,
                branch.branch_name,
                branch.local_commit if branch.local_commit else "N/A",
                branch.local_date.isoformat() if branch.local_date else "N/A",
                branch.remote_commit or "N/A",
                branch.remote_date.isoformat() if branch.remote_date else "N/A",
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

    async def get_local_branches(self) -> list[PackageBranch]:
        """
        Get all local branches of the package repository.
        If the package is not a git repository, it raises an error.
        """
        repository = self.get_local_git_repo()
        branches = []
        for branch in repository.branches:
            branches.append(PackageBranch(
                package_name=self.package.name,
                branch_name=branch.name,
                commit=branch.commit.hexsha,
                date=branch.commit.committed_datetime.astimezone(local_tz)
            ))
        return branches
    
    async def get_local_branch(self, branch_name: str) -> PackageBranch | None:
        found = (branch for branch in await self.get_local_branches() if branch.branch_name == branch_name)
        return next(found, None)

    async def _get_remote_branches(self) -> list[str]:
        """
        Get all remote branches of the package repository.
        If the package is not a git repository, it raises an error.
        """
        if self.pat_token is None:
            raise PackageRepositoryError("Personal Access Token (PAT) is required to access remote branches.")
        async with httpx.AsyncClient() as client:
            try:
                url = f"https://api.github.com/repos/{self.package.repository.owner}/{self.package.repository.name}/branches"
                tokens = self.pat_token if isinstance(self.pat_token, list) else [self.pat_token]
                for token in tokens:
                    headers = {"Authorization": f"token {token.get_secret_value()}"}
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    return [branch['name'] for branch in data]
            except httpx.HTTPStatusError as e:
                console.log(f"Error fetching remote branches: {e}", style="bold red")
                raise
        return []

    async def get_remote_branches(self) -> list[PackageBranch]:
        """
        Get all remote branches of the package repository.
        If the package is not a git repository, it raises an error.
        """
        branch_names = await self._get_remote_branches()
        branches = []
        for branch_name in branch_names:
            remote_branch = await self.get_remote_branch(branch_name)
            if remote_branch:
                branches.append(remote_branch)
        return branches

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

    async def get_branches(self) -> list[PackageBranchWithOrigin]:
        """
        Get all branches of the package repository, both local and remote.
        Returns a list of PackageBranchWithOrigin objects.
        """
        local_branches = await self.get_local_branches()
        remote_branches = await self.get_remote_branches()
        local_branches_dict = {branch.branch_name: branch for branch in local_branches}
        remote_branches_dict = {branch.branch_name: branch for branch in remote_branches}
        names = sorted(set(local_branches_dict).union(set(remote_branches_dict)))
        branches = []
        for name in names:
            local_branch = local_branches_dict.get(name)
            remote_branch = remote_branches_dict.get(name)
            branches.append(PackageBranchWithOrigin(
                package_name=self.package.name,
                branch_name=name,
                local_commit=local_branch.commit if local_branch else None,
                local_date=local_branch.date if local_branch else None,
                remote_commit=remote_branch.commit if remote_branch else None,
                remote_date=remote_branch.date if remote_branch else None
            ))
        return branches

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
                origin_branch = await repository.get_remote_branch(active_branch.branch_name)
                branch = PackageBranchWithOrigin(
                    package_name=package.name,
                    branch_name=active_branch.branch_name,
                    local_commit=active_branch.commit,
                    local_date=active_branch.date,
                    remote_commit=origin_branch.commit if origin_branch else None,
                    remote_date=origin_branch.date if origin_branch else None
                )
                active_branches.append(branch)
            except PackageRepositoryError as e:
                console.log(f"Error with package '{package.name}': {e}", style="bold red")
        return active_branches
