from enum import Enum

import rich.console
from pydantic import HttpUrl, AnyHttpUrl, SecretStr, TypeAdapter


console = rich.console.Console()


HttpUrlAdapter = TypeAdapter(HttpUrl)
AnyHttpUrlAdapter = TypeAdapter(AnyHttpUrl)
SecretStrAdapter = TypeAdapter(SecretStr)


class PackageTypes(Enum):
    PYTHON_UV = "python-uv"
    NODEJS = "nodejs"
