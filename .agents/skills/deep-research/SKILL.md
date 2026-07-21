```markdown
# deep-research Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and conventions used in the `deep-research` Python repository. You'll learn about the project's file organization, import/export styles, commit message habits, and how to approach testing—even in the absence of a formal framework. This guide is ideal for contributors aiming for consistency and best practices in this codebase.

## Coding Conventions

### File Naming
- Use **snake_case** for all Python files.
  - Example: `data_loader.py`, `model_utils.py`

### Import Style
- Use **relative imports** within the package.
  - Example:
    ```python
    from .utils import preprocess_data
    ```

### Export Style
- Use **named exports** (explicitly listing what is exported).
  - Example:
    ```python
    __all__ = ["preprocess_data", "train_model"]
    ```

### Commit Messages
- Freeform style, no strict prefixes.
- Average length: ~35 characters.
  - Example:  
    ```
    Add data preprocessing module
    ```

## Workflows

### Adding a New Module
**Trigger:** When introducing a new feature or utility.
**Command:** `/add-module`

1. Create a new Python file using snake_case, e.g., `feature_extractor.py`.
2. Use relative imports to access shared utilities.
3. Define `__all__` for named exports.
4. Write concise, descriptive commit messages.

### Refactoring Existing Code
**Trigger:** When improving or restructuring code.
**Command:** `/refactor-code`

1. Identify the module to refactor.
2. Apply changes, maintaining snake_case and relative imports.
3. Update `__all__` as needed.
4. Test changes manually or with available test scripts.
5. Commit with a clear message.

### Writing Tests
**Trigger:** When adding or updating test coverage.
**Command:** `/write-test`

1. Create a test file following the `*.test.ts` pattern (if using TypeScript for tests).
2. Place test files alongside or in a dedicated `tests/` directory.
3. Write tests according to the project's conventions.
4. Run tests manually, as the framework is unspecified.

## Testing Patterns

- Test files follow the `*.test.ts` naming pattern, suggesting TypeScript-based tests.
- No specific testing framework detected.
- Place test files in a consistent location (e.g., `tests/` directory).
- Example test file name: `data_loader.test.ts`

## Commands
| Command         | Purpose                                   |
|-----------------|-------------------------------------------|
| /add-module     | Scaffold and add a new Python module      |
| /refactor-code  | Refactor existing code for improvements   |
| /write-test     | Create or update a test file              |
```
