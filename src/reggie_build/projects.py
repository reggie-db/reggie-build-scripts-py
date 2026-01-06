"""
Project management utilities for working with Python projects and pyproject.toml files.

This module provides functionality to discover, load, and manipulate Python projects
within a workspace. It supports:
- Finding projects by name or path
- Reading and modifying pyproject.toml configurations
- Discovering workspace member projects
- Managing project dependencies and relationships

The Project class wraps a pyproject.toml file and provides convenient access to
project metadata.
"""

import fnmatch
import functools
import pathlib
import re
import subprocess
from io import IOBase
from urllib.request import urlopen
from itertools import chain
from os import PathLike
from typing import Iterable, IO, Mapping
from urllib.parse import urlparse, ParseResult

import tomlkit
import typer
from tomlkit import TOMLDocument

from reggie_build import utils


# Standard filename for Python project configuration files
PYPROJECT_FILE_NAME = "pyproject.toml"
_PYPROJECT_SOURCE = Mapping | PathLike | str | bytes | IO | None
_HTTP_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def option(**kwargs):
    """
    Return a Typer option for selecting projects.

    Provides a standard --project/-p option for CLI commands that operate on a
    subset of workspace projects.

    Args:
        **kwargs: Additional keyword arguments to pass to typer.Option

    Returns:
        A Typer Option instance
    """
    return typer.Option(
        "-p",
        "--project",
        help="Optional list of project names or identifiers to sync",
        **kwargs,
    )


@functools.cache
def root() -> "Project":
    """
    Get the root workspace project.

    Returns a cached Project instance representing the root workspace directory.
    The root project is identified by the presence of a pyproject.toml file in the
    repository root directory.

    Returns:
        Project instance for the root workspace
    """
    return Project(root_dir())


def dir(input: PathLike | str, match_member: bool = True) -> pathlib.Path | None:
    """
    Find the project directory for a given input.

    Attempts to locate a project directory by searching for a pyproject.toml file.
    Can resolve paths, directory names, or project names. If match_member is True,
    will also search workspace member projects by name.

    Args:
        input: Path, directory name, or project name to search for
        match_member: If True, search workspace member projects by name when input is a string

    Returns:
        Path to the project directory if found, None otherwise
    """

    def _pyproject_file(path: pathlib.Path | None):
        """
        Recursively search for pyproject.toml file starting from the given path.

        Handles both directory and file paths, traversing up the directory tree
        if necessary to find the configuration file.

        Args:
            path: Starting path to search from

        Returns:
            Path to pyproject.toml file if found, None otherwise
        """
        if path is not None and path.name:
            if path.is_dir():
                return _pyproject_file(path / PYPROJECT_FILE_NAME)
            elif path.name != PYPROJECT_FILE_NAME:
                parent = path.parent
                return _pyproject_file(parent)
            elif path.is_file():
                return path
        return None

    try:
        if f := _pyproject_file(pathlib.Path(input)):
            return f.parent
    except Exception:
        pass
    # Search workspace member projects by name if input is a string
    if match_member and isinstance(input, str):
        root_proj = root()
        for p in chain([root_proj], root_proj.members()):
            if p.name == input:
                return p.dir
    return None


@functools.cache
def root_pyproject() -> "PyProject":
    try:
        if top_level := subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip():
            return PyProject(source=top_level)
    except Exception:
        pass
    for p in [pathlib.Path.cwd(), pathlib.Path(__file__).parent]:
        try:
            return PyProject(source=p)
        except Exception:
            pass
    raise ValueError(f"Root {PYPROJECT_FILE_NAME} not found")


def root_dir() -> pathlib.Path:
    if source_file := root_pyproject().source_file:
        return source_file.parent
    raise ValueError("Root dir not found")


@functools.cache
def scripts_dir() -> pathlib.Path:
    """
    Return the directory containing the scripts project.

    Identifies which workspace member project contains this scripts module by
    checking if the current file is within any member project's directory.

    Returns:
        Path to the scripts project directory

    Raises:
        ValueError: If the scripts directory cannot be found in any member project
    """
    file = pathlib.Path(__file__)
    for p in root().members():
        if file.is_relative_to(p.dir):
            return p.dir
    return file.parent


class PyProject(TOMLDocument):
    def __init__(self, *args, source: _PYPROJECT_SOURCE = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.source = source
        self.reload(_reload_io=True)

    @property
    def source_file(self) -> pathlib.Path | None:
        source = self.source
        if PyProject._to_url(source) is None:
            return PyProject._to_file(source)
        return None

    def reload(self, _reload_io=False) -> bool:
        source = self.source
        data: Mapping | None = None
        if source is None:
            data = dict()
        else:
            if source_url := PyProject._to_url(source):
                with urlopen(source_url.geturl()) as fp:
                    data = tomlkit.load(fp)
            elif source_file := PyProject._to_file(source):
                if source_file.is_file():
                    with source_file.open("r") as fp:
                        data = tomlkit.load(fp)
                else:
                    data = dict()
            elif isinstance(source, (str, bytes)):
                data = tomlkit.parse(source)
            elif isinstance(source, IO):
                if _reload_io:
                    with source as fp:
                        data = tomlkit.load(fp)
            else:
                data = source
        if data is None:
            raise ValueError(f"Reload failed - source:{source}")
        self.clear()
        if data:
            self.update(data)
            return True
        else:
            return False

    def persist(self, force: bool = False) -> bool:
        if source_file := self.source_file:
            text = PyProject._clean_yaml(tomlkit.dumps(self))
            if not force:
                source_file_text = (
                    source_file.read_text() if source_file.exists() else None
                )
                if text == source_file_text:
                    return False
            source_file.parent.mkdir(parents=True, exist_ok=True)
            with source_file.open("w") as fp:
                fp.write(text)
            return True
        raise ValueError(f"Persist failed - source:{self.source}")

    def is_workspace(self) -> bool:
        return (
            True if self.get("tool", {}).get("uv", {}).get("workspace", None) else False
        )

    def __str__(self) -> str:
        out = {}
        if source := self.source:
            out["__source__"] = source
        if value := self.value:
            out.update(value)
        return str(out)

    @staticmethod
    def _to_file(source: _PYPROJECT_SOURCE) -> pathlib.Path | None:
        if source is None:
            return None
        elif isinstance(source, str):
            source = source.strip()
            if not source or "\n" in source or "\r" in source:
                return None
        if isinstance(source, (str, PathLike)):
            try:
                source_path = pathlib.Path(source).resolve()
            except Exception:
                return None
        else:
            return None
        source_path_name_valid = PYPROJECT_FILE_NAME == source_path.name
        if source_path.exists():
            if source_path.is_dir():
                return source_path / PYPROJECT_FILE_NAME
            elif source_path_name_valid and source_path.is_file():
                return source_path
            else:
                return None
        else:
            return (
                source_path
                if source_path_name_valid
                else (source_path / PYPROJECT_FILE_NAME)
            )

    @staticmethod
    def _to_url(source: _PYPROJECT_SOURCE) -> ParseResult | None:
        if isinstance(source, str):
            source = source.strip()
            if bool(_HTTP_URL_RE.match(source)):
                try:
                    return urlparse(source)
                except Exception:
                    pass
        return None

    @staticmethod
    def _clean_yaml(yaml: str) -> str | None:
        if yaml:
            yaml = yaml.strip()
        if not yaml:
            return None
        lines = yaml.splitlines()
        out = []
        prev_blank = False

        for line in lines:
            blank = not line.strip()
            if blank and prev_blank:
                continue
            out.append(line)
            prev_blank = blank

        yaml = "\n".join(out).strip()
        return yaml + "\n" if yaml else ""


def _workspace_tree():
    args = ["uv", "tree", "--verbose"]
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    assert proc.stderr is not None

    for line in proc.stderr:
        print(line)

    rc = proc.wait()
    if rc != 0:
        raise subprocess.CalledProcessError(rc, args)


class Project:
    """
    Represents a Python project with its pyproject.toml configuration.

    Provides access to project metadata, configuration, and workspace relationships.
    The pyproject attribute is a TOML document that can be modified and persisted
    back to the pyproject.toml file.
    """

    def __init__(self, path: PathLike | str):
        """
        Initialize a Project instance from a path or project name.

        Locates the project directory, loads the pyproject.toml file, and parses
        it into a mutable TOML document for easy manipulation.

        Args:
            path: Path to project directory, pyproject.toml file, or project name

        Raises:
            ValueError: If the project directory cannot be found or if pyproject.toml
                        cannot be parsed
        """
        self.dir = dir(path)
        if not self.dir:
            raise ValueError(f"Project dir not found: {path}")
        self.pyproject_file = self.dir / PYPROJECT_FILE_NAME
        try:
            pyproject_text = self.pyproject_file.read_text().rstrip()
            # Ensure trailing newline for proper TOML parsing
            if pyproject_text:
                pyproject_text += "\n"
            self.pyproject = tomlkit.parse(pyproject_text)

        except Exception as e:
            raise ValueError(
                f"Project {PYPROJECT_FILE_NAME} error - path:{self.pyproject_file} error:{e}"
            )

    @property
    def name(self):
        """
        Get the project name.

        Returns the name from pyproject.toml's project.name field, or falls back
        to the directory name if not specified.

        Returns:
            Project name string
        """
        project_name = utils.mapping_get(self.pyproject, "project", "name")
        return project_name or self.dir.name

    @property
    def is_root(self) -> bool:
        """
        Check if this project is the root workspace project.

        Returns:
            True if this project is the root workspace, False otherwise
        """
        return root_dir() == self.dir

    def members(self) -> Iterable["Project"]:
        """
        Get all workspace member projects.

        Yields Project instances for each member project defined in this project's
        tool.uv.workspace.members configuration. Only includes members that match
        the include patterns and don't match exclude patterns.

        Yields:
            Project instances for each member project
        """
        for member_dir in self.member_dirs():
            yield Project(member_dir)

    def member_dirs(self) -> Iterable[pathlib.Path]:
        """
        Get directory paths for all workspace member projects.

        Scans the project directory for subdirectories that match the workspace
        member patterns defined in tool.uv.workspace.members and don't match
        exclude patterns. Only returns directories that contain valid pyproject.toml files.

        Yields:
            Path objects for each valid member project directory
        """
        members = utils.mapping_get(
            self.pyproject, "tool", "uv", "workspace", "members", default=[]
        )
        exclude = utils.mapping_get(
            self.pyproject, "tool", "uv", "workspace", "exclude", default=[]
        )

        def match_any(name, patterns):
            """
            Check if a name matches any pattern using fnmatch glob matching.

            Args:
                name: Name to check
                patterns: List of glob patterns to match against

            Returns:
                True if name matches any pattern, False otherwise
            """
            return any(fnmatch.fnmatch(name, pat) for pat in patterns)

        for path in self.dir.iterdir():
            if not path.is_dir():
                continue
            name = path.name
            # Include if matches member patterns and doesn't match exclude patterns
            if match_any(name, members) and not match_any(name, exclude):
                if member_dir := dir(path):
                    yield member_dir

    def __str__(self):
        """
        Return a string representation of the project.

        Returns:
            String showing the project name and directory name
        """
        return f"{Project.__name__}(name={self.name!r} dir={self.dir.name!r})"


if __name__ == "__main__":
    _workspace_tree()
    dir = root_dir()
    print(PyProject(source=dir))
    # print(PyProject(source="https://raw.githubusercontent.com/reggie-db/reggie-build-py/refs/heads/main/pyproject.toml").persist())
    proj = PyProject(source="/Users/reggie.pierce/Projects/reggie-build-py")
    print(proj)
    print(proj.reload())
    print(proj)
    print(proj.persist())
    print(
        PyProject(source="/Users/reggie.pierce/Projects/reggie-build-py").is_workspace()
    )
    print(
        PyProject(
            source="/Users/reggie.pierce/Projects/reggie-bricks-py/pyproject.toml"
        ).is_workspace()
    )
    print(root_dir())
