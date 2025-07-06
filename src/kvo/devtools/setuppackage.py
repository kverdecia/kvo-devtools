from .package import Package
from .dependencies import install_dependencies
from .packageindexes import PackageIndex


async def setup_package(package: Package, package_index: PackageIndex | None = None) -> None:
    """
    Sets up the package by downloading it and installing its dependencies.
    This method is an asynchronous wrapper for the download and install_deps methods.
    """
    await package.download()
    await install_dependencies(package, package_index)
