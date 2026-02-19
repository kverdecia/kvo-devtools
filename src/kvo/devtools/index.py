import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, FilePath
from pydantic_settings import BaseSettings

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


class IndexSettings(BaseSettings):
    index_file: FilePath = Field('./kvo-devtools.json', description="Path to the index.json file.")

    model_config = ConfigDict(extra='ignore', env_prefix='KVO_DEVTOOLS_')

    def load_index(self) -> Index:
        """
        Loads the index from the specified index file.
        Returns the loaded Index object.
        """
        return Index.model_validate_json(self.index_file.read_text())

    @property
    def default_index_schema_path(self) -> Path:
        """
        Returns the default path to the index schema file.
        The default path if formed by the index file path but with the extension changed to .schema.json.
        """
        return self.index_file.with_suffix('.schema.json')

    def generate_index_schema(self, schema_file_path: Path | None = None, override: bool = False) -> None:
        """
        Generates the JSON schema for the Index model and saves it to the default index schema path.
        """
        if schema_file_path is None:
            schema_file_path = Path(self.default_index_schema_path)
        if schema_file_path.exists() and not override:
            raise FileExistsError(f"Schema file {schema_file_path} already exists. Use override=True to overwrite it.")
        schema = Index.model_json_schema()
        schema_file_path.write_text(json.dumps(schema, indent=4))
