"""
Workspace discovery and metadata utilities.

This module provides classes and functions for discovering Python workspaces
using `uv workspace metadata` command. Features include:
- Workspace metadata discovery from uv
- Hierarchical workspace node structure (root and members)
- Git repository name detection as fallback
- Automatic root project detection

The WorkspaceNode class provides structured access to workspace information
in a tree structure without directly parsing pyproject.toml files.
"""

import json
import logging
import pathlib
from dataclasses import asdict, dataclass, field
from itertools import chain
from os import PathLike
from typing import Iterable

import typer

from reggie_build import projects, utils

LOG = utils.logger(__file__)


@dataclass
class WorkspaceNode:
    """
    Represents a node in the workspace hierarchy (root or member project).

    Attributes:
        name: Project name
        path: Absolute path to the project directory
        root: Whether this is the root workspace node
        members: List of child member nodes (only populated for root)
    """

    name: str
    path: pathlib.Path
    root: bool = field(default=False)
    members: list["WorkspaceNode"] = field(default_factory=list)

    @property
    def pyproject_path(self) -> pathlib.Path:
        """Get the path to the pyproject.toml file for this node."""
        return self.path / projects.PYPROJECT_FILE_NAME

    def nodes(self) -> Iterable["WorkspaceNode"]:
        """Iterate over all nodes (self and members)."""
        return chain([self], self.members)

    def __post_init__(self):
        """Validate that only root nodes have members."""
        if self.members:
            if not self.root:
                raise ValueError(f"Non root nodes must not have members: {self}")
            for member in self.members:
                if member.root:
                    raise ValueError(f"Member nodes must not be root: {self}")


def root_node(
    cwd: PathLike | str | None = None, ctx: typer.Context | None = None
) -> WorkspaceNode:
    """
    Get the root workspace node, optionally with context caching.

    When ctx is provided, caches the result in the context to avoid
    reloading. Without ctx, directly calls _root_node().

    Args:
        cwd: Working directory to discover workspace from
        ctx: Optional Typer context for caching

    Returns:
        WorkspaceNode representing the root with populated members list
    """
    if ctx is None:
        return _root_node(cwd)
    cache_key = f"workspace_root_node_{cwd or pathlib.Path().cwd()}"
    return utils.command_meta_cache(ctx, cache_key, lambda: _root_node(cwd))


def _root_node(cwd: PathLike | str | None = None) -> WorkspaceNode:
    """
    Get the root workspace node with all member nodes.

    Executes `uv workspace metadata` to discover the workspace structure,
    identifies the root project, and creates member nodes for all workspace
    members. Falls back to git repo name if root is not explicitly listed.

    Args:
        cwd: Working directory to discover workspace from, or None for current directory

    Returns:
        WorkspaceNode representing the root with populated members list
    """
    metadata_data = _uv_metadata(cwd=cwd)
    root_path = pathlib.Path(metadata_data["workspace_root"])
    root_name: str | None = None
    member_nodes: list[WorkspaceNode] = []
    for member_data in metadata_data["members"]:
        name = member_data["name"]
        path = pathlib.Path(member_data["path"])
        if root_path == path:
            if root_name is None:
                root_name = name
            else:
                raise ValueError("Multiple workspace roots found")
        else:
            member_nodes.append(WorkspaceNode(name=name, path=path))
    if root_name is None:
        root_name = utils.git_repo_name(cwd=cwd)
        if not root_name:
            root_name = root_path.name
    return WorkspaceNode(
        name=root_name, path=root_path, root=True, members=member_nodes
    )


def node(
    source: PathLike | str | None = None,
    cwd: PathLike | str | None = None,
    ctx: typer.Context | None = None,
) -> WorkspaceNode | None:
    """
    Find a workspace node by name or path.

    Searches the workspace tree for a node matching the source identifier.
    Supports name-based lookup and path-based lookup.

    Args:
        source: Node name or path to find, or None for root node
        cwd: Working directory to discover workspace from
        ctx: Optional Typer context for caching

    Returns:
        WorkspaceNode if found, None if not found
        If source is None, returns the root node

    Example:
        node("my-project")  # Find by name
        node("/path/to/project")  # Find by path
        node()  # Returns root
    """
    rnode = root_node(cwd=cwd, ctx=ctx)
    if not source:
        return rnode
    for n in rnode.nodes():
        if n.name == source:
            return n
        if pathlib.Path(source) == n.path:
            return n
    return None


def _uv_metadata(cwd: PathLike | str | None = None) -> dict:
    """
    Execute uv workspace metadata command and parse the result.

    Args:
        cwd: Working directory to run command in

    Returns:
        Parsed metadata dictionary from uv
    """
    args = ["uv", "workspace", "metadata"]
    stdout = utils.exec(args, cwd=cwd, stderr_log_level=logging.ERROR)
    LOG.debug("UV metadata: %s", stdout)
    return json.loads(stdout)


if "__main__" == __name__:
    rnode = root_node("/Users/reggie.pierce/Projects/reggie-bricks-py")
    print(
        json.dumps(
            asdict(rnode),
            indent=2,
            default=str,
        )
    )
    for node in rnode.nodes():
        print(
            json.dumps(
                asdict(node),
                indent=2,
                default=str,
            )
        )
