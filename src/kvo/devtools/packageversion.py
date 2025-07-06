import abc
import importlib.metadata
import json
import asyncio
import subprocess

from pydantic import BaseModel

from .package import Package


class PackageVersion(BaseModel, metaclass=abc.ABCMeta):
    package: Package

    @abc.abstractmethod
    async def get_version(self) -> str | None:
        ...

    @staticmethod
    def from_package(package: Package) -> 'PackageVersion':
        if package.type is None:
            raise ValueError("Package type is not set for this package.")
        entrypoints_group_name = 'kvo-devtools-package-version'
        entrypoints = importlib.metadata.entry_points(group=entrypoints_group_name)
        if not entrypoints:
            raise ValueError(f"No entry points found for group '{entrypoints_group_name}'. Ensure you have registered the package version retriever for package type '{package.type}'.")
        entrypoint = next((ep for ep in entrypoints if ep.name == package.type.value), None)
        if entrypoint is None:
            raise ValueError(f"No entry point found for package type '{package.type}' in group '{entrypoints_group_name}'. Ensure you have registered the package version retriever for package type '{package.type}'.")
        VersionRetriever = entrypoint.load()
        if not issubclass(VersionRetriever, PackageVersion):
            raise ValueError(f"The entry point '{entrypoint.name}' does not point to a valid DependenciesInstaller subclass.")
        return VersionRetriever(package=package)


class NodeJsPackageVersion(PackageVersion):
    async def get_version(self) -> str | None:
        package_json_path = self.package.path / 'package.json'
        if not package_json_path.is_file():
            raise FileNotFoundError(f"package.json not found in {self.package.path}")
        content = package_json_path.read_text()
        data = json.loads(content)
        return data.get('version', None)


class PythonPackageVersion(PackageVersion):
    async def get_version(self) -> str | None:
        python_src = f"""from importlib.metadata import version; print(version("{self.package.name}"))"""
        command = ['uv', 'run', 'python', '-c', python_src]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.package.path,
            start_new_session=True,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise ValueError(
                f"Error fetching retrieving version from Python package '{self.package.name}': {stderr.decode('utf-8') if stderr else ''}"
            )
        return stdout.decode('utf-8').strip() if stdout else None
