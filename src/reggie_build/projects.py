"""
Project management utilities for working with Python projects and pyproject.toml files.

This module provides the PyProject class and project() factory function for:
- Loading and persisting pyproject.toml files
- Context-based caching with automatic persistence
- Flexible source resolution (name, path, or default to root)
- Automatic formatting and pruning of empty sections

The project() function is the primary entry point, providing intelligent
source resolution and context caching when available.
"""

import pathlib
from os import PathLike

import tomlkit
import typer
from tomlkit import TOMLDocument

from reggie_build import utils, workspaces

PYPROJECT_FILE_NAME = "pyproject.toml"
LOG = utils.logger(__file__)


class PyProject(TOMLDocument):
    """
    A Python project represented by its pyproject.toml configuration.

    Extends tomlkit.TOMLDocument to provide structured access and persistence.
    Use the project() factory function for intelligent loading with caching.

    Attributes:
        path: Path to the pyproject.toml file
    """

    def __init__(
        self,
        path: pathlib.Path,
        load: bool = True,
        **kwargs,
    ):
        """
        Initialize a PyProject from a file path.

        Note: Prefer using project() factory function for intelligent
        source resolution and context caching.

        Args:
            path: Path to pyproject.toml file
            load: Whether to immediately load the file contents
            **kwargs: Additional arguments passed to TOMLDocument
        """
        super().__init__(**kwargs)
        self.path = path
        if load:
            self.reload()

    def reload(self):
        """
        Reload the pyproject.toml file from disk.

        Clears current contents and reloads from the source file.
        """
        if self.path.exists():
            with self.path.open("r") as fp:
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
        if not force:
            file_text = self.path.read_text() if self.path.exists() else None
            if text == file_text:
                return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as fp:
            fp.write(text)
        return True


def project(
    source: PathLike | str | None = None,
    cwd: PathLike | str | None = None,
    ctx: typer.Context = None,
) -> "PyProject":
    """
    Load a PyProject with intelligent source resolution and caching.

    Resolves the source to a pyproject.toml path and loads it. When a context
    is provided, caches the instance and registers automatic persistence on close.

    Args:
        source: Project identifier - node name, file path, or None for root
        cwd: Working directory for workspace discovery
        ctx: Optional Typer context for caching and auto-persistence

    Returns:
        PyProject instance (cached in context if ctx provided)

    Resolution order:
        1. If source is None: use root workspace node
        2. If source is not PathLike: try as workspace node name
        3. Otherwise: treat as file path

    Example:
        project()                    # Root project
        project("my-member")         # Member by name
        project("/path/to/proj")     # Explicit path
        project("my-member", ctx=ctx)  # With caching
    """
    if not source:
        path = workspaces.root_node(cwd=cwd, ctx=ctx).pyproject_path
    elif not isinstance(source, PathLike):
        node = workspaces.node(source, cwd=cwd, ctx=ctx)
        if node:
            path = node.pyproject_path
        else:
            path = pathlib.Path(source)
    else:
        path = pathlib.Path(source)
    if ctx is None:
        return PyProject(path)
    key = f"pyproject_{path.absolute().as_posix()}"

    def _on_close(pyproject: PyProject):
        """Persist PyProject on context close if modified."""
        if pyproject.persist():
            file_path = str(pyproject.path)
            name = pyproject.get("project", {}).get("name", file_path)
            message = f"Persisted {name}"
            if file_path != name:
                message += f": {file_path}"
            LOG.info(message)

    return utils.command_meta_cache(
        ctx, key, lambda: PyProject(path), on_close=_on_close
    )


if __name__ == "__main__":
    pass
