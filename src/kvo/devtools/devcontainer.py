import json
import argparse
from pathlib import Path

from pydantic import BaseModel, field_validator

from .package import Package


class DevContainer(BaseModel):
    package: Package
    _devcontainer_config: dict = None

    @field_validator('package', mode='after')
    @classmethod
    def validate_package(cls, package, info):
        """
        Validates and adjusts the site directories to be absolute if they're relative.
        """
        cls.get_package_devcontainer_file(package)
        return package

    @staticmethod
    def get_package_devcontainer_file(package: Package) -> Path:
        if (package.path / ".devcontainer.json").exists():
            return package.path / ".devcontainer.json"
        if (package.path / ".devcontainer" / "devcontainer.json").exists():
            return package.path / ".devcontainer" / "devcontainer.json"
        raise ValueError(f"No devcontainer.json found for package {package.name}")

    @property
    def devcontainer_file(self) -> Path:
        return self.get_package_devcontainer_file(self.package)

    def load_devcontainer_config(self) -> dict:
        with self.devcontainer_file.open('r') as stream:
            return json.load(stream)

    @property
    def devcontainer_config(self) -> dict:
        if self._devcontainer_config is None:
            self._devcontainer_config = self.load_devcontainer_config()
        return self._devcontainer_config

    @property
    def name(self) -> str:
        return self.devcontainer_config['name']

    @property
    def container_name(self) -> str | None:
        run_args = self.devcontainer_config.get('runArgs', [])
        if not run_args:
            return None
        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('--name', type=str)
        namespace, _ = arg_parser.parse_known_args(run_args)
        return namespace.name
