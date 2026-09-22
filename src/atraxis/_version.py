"""Installed package version."""

from importlib.metadata import PackageNotFoundError, version

try:
    PACKAGE_VERSION = version("atraxis-sdk")
except PackageNotFoundError:
    PACKAGE_VERSION = "0+unknown"
