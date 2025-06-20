from pydantic import BaseModel, ConfigDict, Field

from .package import Package


class Index(BaseModel):
    index_schema: str | None = Field(default=None, description="Address of a file with the schema definition of the index.json.", alias='$schema')
    packages: list[Package] = []

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
