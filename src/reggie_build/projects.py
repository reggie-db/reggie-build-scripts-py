"""
Project management utilities for working with Python projects and pyproject.toml files.

This module provides functionality to discover, load, and manipulate Python projects
within a workspace. The PyProject class extends tomlkit.TOMLDocument to provide:
- Convenient access to pyproject.toml files
- Project metadata discovery (name, root status, workspace integration)
- Iteration over workspace members
- Persistence with automatic pruning and formatting
- Integration with workspace metadata from uv

The PyProject class wraps a pyproject.toml file and provides structured access to
project metadata while maintaining TOML formatting and structure.
"""

import pathlib
from itertools import chain
from typing import Iterable

import tomlkit
from tomlkit import TOMLDocument

from reggie_build import utils, workspaces
from reggie_build.workspaces import WorkspaceMetadata, WorkspaceProject

# Standard filename for Python project configuration files
PYPROJECT_FILE_NAME = "pyproject.toml"


def root() -> "PyProject":
    """
    Get the root PyProject for the current workspace.

    Returns:
        PyProject instance for the workspace root
    """
    metadata = workspaces.metadata()
    return PyProject(source=metadata)


class PyProject(TOMLDocument):
    """
    A Python project represented by its pyproject.toml configuration.

    Extends tomlkit.TOMLDocument to provide structured access to project metadata
    and workspace relationships. Supports loading from:
    - WorkspaceMetadata (root project)
    - WorkspaceProject (member project)
    - pathlib.Path (directory or pyproject.toml file)

    Attributes:
        source: The source used to locate the pyproject.toml file
    """

    def __init__(
        self,
        source: WorkspaceMetadata | WorkspaceProject | pathlib.Path,
        load: bool = True,
        **kwargs,
    ):
        """
        Initialize a PyProject from a source.

        Args:
            source: WorkspaceMetadata, WorkspaceProject, or Path to pyproject.toml
            load: Whether to immediately load the file contents
            **kwargs: Additional arguments passed to TOMLDocument
        """
        super().__init__(**kwargs)
        self.source = source
        if load:
            self.reload()
        else:
            assert self.file

    @property
    def file(self) -> pathlib.Path:
        """
        Get the path to the pyproject.toml file.

        Returns:
            Path to the pyproject.toml file
        """
        source_dir = (
            self.source.workspace_root
            if isinstance(self.source, WorkspaceMetadata)
            else self.source.path
            if isinstance(self.source, WorkspaceProject)
            else self.source
            if self.source.is_dir()
            else None
        )
        if source_dir:
            return source_dir / PYPROJECT_FILE_NAME
        path = self.source
        name_valid = PYPROJECT_FILE_NAME == path.name
        if path.is_file():
            if name_valid:
                return path
            raise ValueError(f"Invalid {PYPROJECT_FILE_NAME} - source:{self.source}")
        elif name_valid:
            return path
        else:
            return path / PYPROJECT_FILE_NAME

    @property
    def name(self) -> str:
        """
        Get the project name.

        Returns the name from [project] section, workspace project name, or directory name.

        Returns:
            Project name string
        """
        name = self.get("project", {}).get("name", None)
        if name is not None:
            return name
        if workspace_project := self.workspace_project():
            return workspace_project.name
        else:
            return self.file.parent.name

    def is_root(self) -> bool:
        """Check if this is the workspace root project."""
        return isinstance(self.source, WorkspaceMetadata)

    def is_project(self) -> bool:
        """Check if this has a [project] section (is a Python project)."""
        if self.get("project", None):
            return True
        else:
            return False

    def workspace_project(self) -> WorkspaceProject | None:
        """
        Get the associated WorkspaceProject.

        Returns:
            WorkspaceProject instance or None if not from workspace metadata
        """
        return (
            self.source.root
            if isinstance(self.source, WorkspaceMetadata)
            else self.source
            if isinstance(self.source, WorkspaceProject)
            else None
        )

    def projects(self) -> Iterable["PyProject"]:
        """
        Iterate over all projects including self and members.

        Yields only projects with a [project] section.

        Yields:
            PyProject instances for all workspace projects
        """
        for p in chain([self], self.members()):
            if p.is_project():
                yield p

    def members(self) -> Iterable["PyProject"]:
        """
        Iterate over workspace member projects (excluding self).

        Only works for root projects (WorkspaceMetadata sources).

        Yields:
            PyProject instances for member projects
        """
        if isinstance(self.source, WorkspaceMetadata):
            workspace_project_root = self.source.root
            for workspace_project in self.source.members:
                if workspace_project_root != workspace_project:
                    yield PyProject(source=workspace_project)

    def reload(self):
        """
        Reload the pyproject.toml file from disk.

        Clears current contents and reloads from the source file.
        """
        source_file = self.file
        if source_file.exists():
            with source_file.open("r") as fp:
                data = tomlkit.load(fp)
        else:
            data = None
        self.clear()
        if data:
            self.update(data)

    def persist(
        self, prune: bool = True, clean: bool = True, force: bool = False
    ) -> bool:
        """
        Write the pyproject.toml back to disk.

        Args:
            prune: Remove empty collections before writing
            clean: Clean up formatting (whitespace, etc)
            force: Write even if content hasn't changed

        Returns:
            True if file was written, False if no changes detected
        """
        if prune:
            utils.mapping_prune(self)
        text = tomlkit.dumps(self)
        if clean:
            text = utils.clean_text(text)
        source_file = self.file
        if not force:
            source_file_text = source_file.read_text() if source_file.exists() else None
            if text == source_file_text:
                return False
        source_file.parent.mkdir(parents=True, exist_ok=True)
        with source_file.open("w") as fp:
            fp.write(text)
        return True


if __name__ == "__main__":
    print(root().name)
    print(root().is_root())
    proj = PyProject(
        source=workspaces.metadata("/Users/reggie.pierce/Projects/reggie-bricks-py")
    )
    print(proj.name)
    print(proj.is_root())
    for member in proj.members():
        print(member.is_root())
        print(member)
