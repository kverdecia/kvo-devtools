from pydantic import BaseModel

from .package import Package


class Index(BaseModel):
    packages: list[Package] = []

    def find_package(self, name: str) -> Package | None:
        """
        Finds a package by its name in the index.
        Returns the package if found, otherwise returns None.
        """
        for package in self.packages:
            if package.name == name:
                return package
        return None
