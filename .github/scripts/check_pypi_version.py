"""Fail closed when a downloaded release wheel is older than a published version."""

import argparse
import email
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from zipfile import ZipFile

from packaging.version import Version


def check_version(candidate: str, releases: dict) -> None:
    """Reject a candidate when PyPI already has a newer nonempty release."""
    version = Version(candidate)
    newer = [Version(value) for value, files in releases.items() if files and Version(value) > version]
    if newer:
        raise ValueError(f"Refusing superseded {version}: PyPI already contains {max(newer)}")


def fetch_releases(project: str) -> dict:
    try:
        with urlopen(f"https://pypi.org/pypi/{project}/json", timeout=30) as response:
            return json.load(response)["releases"]
    except HTTPError as exc:
        if project != "kwik-e-gate" or exc.code != 404:
            raise
        return {}


def main() -> None:
    """Validate the sole downloaded wheel against current PyPI releases."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", choices=("hermes-gate", "kwik-e-gate"), default="hermes-gate")
    project = parser.parse_args().project
    wheels = list(Path("dist").glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("Expected exactly one release wheel")
    with ZipFile(wheels[0]) as wheel:
        metadata_path, = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        metadata = email.message_from_bytes(wheel.read(metadata_path))
    if metadata["Name"] != project:
        raise ValueError(f"Expected a {project} wheel")
    check_version(metadata["Version"], fetch_releases(project))


if __name__ == "__main__":
    main()
