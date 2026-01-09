import functools
import json
import logging
import pathlib
import subprocess
from dataclasses import dataclass

import dacite
from dacite import from_dict

"""
Interface for uv workspace metadata.

Provides utilities for retrieving and parsing metadata from a uv workspace,
enabling easy access to the workspace root and its member projects.
"""

LOG = logging.getLogger(__name__)


@dataclass
class Metadata:
    """
    Metadata representation of a uv workspace.
    """

    workspace_root: pathlib.Path
    members: list["MetadataMember"]


@dataclass
class MetadataMember:
    """
    Representation of a member project within a uv workspace.
    """

    name: str
    path: pathlib.Path


def metadata(path: pathlib.Path = None) -> Metadata:
    if path is None:
        path = pathlib.Path().cwd()
    return _metadata(path.absolute())


@functools.lru_cache(maxsize=None)
def _metadata(path: pathlib.Path) -> Metadata:
    """
    Retrieve and parse metadata from the uv workspace.

    Executes 'uv workspace metadata' and returns a Metadata instance.
    The result is cached to avoid redundant subprocess calls.
    """
    args = ["uv", "workspace", "metadata"]
    proc = subprocess.run(
        args,
        text=True,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=path,
    )
    if proc.returncode != 0:
        LOG.warning("Failed to execute workspace metadata: %s", proc.stderr)
        raise subprocess.CalledProcessError(
            returncode=proc.returncode, cmd=args, output=proc.stdout, stderr=proc.stderr
        )
    data = json.loads(proc.stdout)
    return from_dict(
        data_class=Metadata,
        data=data,
        config=dacite.Config(type_hooks={pathlib.Path: pathlib.Path}),
    )


def root_dir() -> pathlib.Path:
    """
    Return the root directory of the uv workspace.
    """
    return metadata().workspace_root
