from pydantic import BaseModel, ConfigDict, Field

from .package import Package
from .packageindexes import PackageIndex
from .certificates import Certificates
from .caddy import Caddy


class Index(BaseModel):
    index_schema: str | None = Field(default=None, description="Address of a file with the schema definition of the index.json.", alias='$schema')
    packages: list[Package] = []
    certificates: Certificates | None = None
    package_indexes: list[PackageIndex] = []
    caddy: Caddy | None = None

    model_config = ConfigDict(extra='forbid')

    def find_package(self, name: str) -> Package | None:
        """
        Finds a package by its name in the index.
        Returns the package if found, otherwise returns None.
        """
        for package in self.packages:
            if package.name == name:
                return package
        return None

    def find_package_index(self, name: str) -> PackageIndex | None:
        """
        Finds a package index by its name in the index.
        Returns the package index if found, otherwise returns None.
        """
        for package_index in self.package_indexes:
            if package_index.name == name:
                return package_index
        return None
