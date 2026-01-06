# Agent Tasks: Code Documentation and Cleanup

This document outlines common code cleanup and documentation maintenance tasks that can be performed systematically on this codebase.

## Documentation Review and Sync

### Task: Complete Documentation Audit

**Trigger**: After major refactoring, architecture changes, or before releases

**Steps**:

1. **Review all module-level docstrings**
   - Ensure every `.py` file has a comprehensive module docstring
   - Check that docstrings accurately describe current functionality
   - Update any references to renamed or removed modules
   
   ```bash
   # Check for missing module docstrings
   for file in src/reggie_build/*.py; do
     head -20 "$file" | grep -q '"""' || echo "Missing docstring: $file"
   done
   ```

2. **Verify class and function documentation**
   - Check that all public classes have docstrings with:
     - Purpose description
     - Attribute documentation
     - Usage examples (where appropriate)
   - Ensure non-trivial functions have docstrings with:
     - Purpose description
     - Args documentation
     - Returns documentation
     - Example usage (for complex functions)
   
3. **Update Typer command documentation**
   - All command arguments should use `Annotated` with help text
   - Command docstrings become CLI help text
   - Keep help text concise but informative
   
   ```python
   @app.command()
   def my_command(
       arg: Annotated[str, typer.Argument(help="Description here")],
   ):
       """
       Brief one-line description.
       
       More detailed explanation of what the command does,
       including behavior and side effects.
       """
   ```

4. **Sync README with codebase**
   - Update module reference section for any:
     - New modules added
     - Renamed classes/functions
     - Removed functionality
     - Changed APIs
   - Update dependency list in README
   - Verify all examples still work
   
5. **Update command help blocks**
   ```bash
   uv run reggie-build readme update-cmd
   ```
   - This automatically syncs all `<!-- BEGIN:cmd ... -->` blocks
   - Review the changes to ensure formatting is acceptable

6. **Run linter checks**
   ```bash
   uv run ruff check src/reggie_build/
   read_lints src/reggie_build/
   ```

## Specific Documentation Patterns

### Module Docstring Template

```python
"""
Brief module description (one line).

More detailed explanation of what this module provides. Features include:
- Feature 1
- Feature 2
- Feature 3

Additional context about when/how to use this module.
"""
```

### Class Docstring Template

```python
class MyClass:
    """
    Brief class description.
    
    More detailed explanation of the class purpose and behavior.
    
    Attributes:
        attr1: Description of attribute1
        attr2: Description of attribute2
    """
```

### Function Docstring Template

```python
def my_function(arg1: str, arg2: int = 0) -> bool:
    """
    Brief function description.
    
    More detailed explanation of what the function does,
    including any side effects or important behavior.
    
    Args:
        arg1: Description of arg1
        arg2: Description of arg2 (default 0)
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When this happens
        
    Example:
        >>> my_function("test", 5)
        True
    """
```

### Inline Helper Function Pattern

```python
def outer_function():
    """Main function docstring."""
    
    def _helper(value: Any) -> Any:
        """Brief description of what this helper does."""
        # Implementation
        pass
    
    # Use helper
    result = _helper(data)
```

## Refactoring Documentation Updates

### After Major Architectural Changes

**Checklist**:

- [ ] Update all module docstrings mentioning affected components
- [ ] Search for old class/function names in all docstrings
- [ ] Update README module reference section
- [ ] Check for outdated import examples
- [ ] Update any architectural diagrams or descriptions
- [ ] Verify all code examples still work
- [ ] Update dependency documentation if packages changed

**Commands**:

```bash
# Search for references to old names
grep -r "OldClassName" src/ README.md

# Search for outdated imports
grep -r "from old_module import" src/

# Check for orphaned documentation
git diff --stat  # Look for removed files that might be documented
```

## Automated Documentation Tasks

### 1. Update Command Help in README

```bash
uv run reggie-build readme update-cmd
```

**What it does**:
- Finds all `<!-- BEGIN:cmd ... -->` sentinel blocks
- Executes the commands with `--help`
- Replaces block content with formatted command output
- Filters out `--help` option rows for cleaner output

### 2. Format Code

```bash
uv run reggie-build sync ruff
```

### 3. Clean Build Artifacts

```bash
uv run reggie-build clean build-artifacts
```

## Common Documentation Issues

### Issue: Outdated Class References

**Symptom**: Documentation mentions `Project` but code uses `PyProject`

**Fix**:
```bash
# Find all references
grep -r "Project class" src/ README.md

# Update systematically
# - Module docstrings
# - README module reference
# - Code examples
```

### Issue: Missing Dependency Documentation

**Symptom**: `import tomlkit` but no mention in README dependencies

**Fix**:
- Review `pyproject.toml` dependencies
- Update README "Dependencies" section
- Remove any dependencies that were removed

### Issue: Stale Function Signatures in Docs

**Symptom**: Docstring shows `def func(arg1, arg2)` but signature is `def func(arg1)`

**Fix**:
- Review all docstrings after signature changes
- Use IDE refactoring when possible
- Search for old parameter names

## Documentation Quality Checks

### Before Committing Documentation Changes

```bash
# 1. Check for linter errors
uv run ruff check src/reggie_build/

# 2. Verify all files have docstrings
for file in src/reggie_build/*.py; do
  head -20 "$file" | grep -q '"""' || echo "Missing: $file"
done

# 3. Update command help
uv run reggie-build readme update-cmd

# 4. Check for common typos
grep -r "recieve\|occured\|seperate" src/ README.md

# 5. Verify examples work
# (manually test any code examples in README)
```

## Continuous Maintenance

### Weekly Tasks

- [ ] Run `uv run reggie-build readme update-cmd` to keep CLI help current
- [ ] Check for new linter warnings
- [ ] Review recent commits for documentation drift

### Before Each Release

- [ ] Complete documentation audit (see above)
- [ ] Update version references
- [ ] Verify all examples work
- [ ] Update changelog
- [ ] Review and update module reference section

### After Major Refactoring

- [ ] Search for old names in all documentation
- [ ] Update architecture descriptions
- [ ] Verify import examples
- [ ] Update dependency list
- [ ] Regenerate command help blocks

## Tools and Scripts

### Useful Commands

```bash
# Find all TODOs in docstrings
grep -r "TODO:" src/ --include="*.py"

# Find functions without docstrings (basic check)
grep -B 1 "^def " src/reggie_build/*.py | grep -v '"""'

# Check docstring coverage with ruff
uv run ruff check src/ --select D

# Find long lines in docstrings
grep -r '""".*.\{100,\}' src/

# Update all command help blocks in README
uv run reggie-build readme update-cmd

# Preview README changes without writing
uv run reggie-build readme update-cmd --no-write
```

## Agent Workflow Example

### Task: "Review all docs and ensure they match code"

```
1. List all Python files
   └─> For each file:
       ├─ Check for module docstring
       ├─ Review class docstrings
       ├─ Check function docstrings
       └─ Note any mismatches with code

2. Review projects.py specifically
   └─> Check for renamed classes (Project → PyProject)
   └─> Update references

3. Check for new modules
   └─> workspaces.py was added
   └─> Add documentation
   └─> Update README module reference

4. Update README
   ├─ Module reference section
   ├─ Dependency list
   └─ Run `readme update-cmd`

5. Verify all changes
   ├─ Run linter
   ├─ Check git diff
   └─> Confirm accuracy
```

## Related Documentation

- See `README.md` for user-facing documentation
- See `pyproject.toml` for dependency list
- See `src/reggie_build/readme.py` for README automation implementation

