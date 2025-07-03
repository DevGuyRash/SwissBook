# Instructions

## 🐙 Git Workflow

If, and only if, you are operating within a Git repository (i.e., a `.git` directory exists), you MUST adhere to the following workflow. Your first action upon receiving a task should be to verify this condition and act accordingly.

### Branching Strategy

1. **Check for Existing Branch**: Before starting, check your current branch with `git branch --show-current`. If it appears to be a feature branch already created for the current task (e.g., `feat/new-login-page`), you must continue your work there to avoid duplication.
2. **Create a New Branch**: If you are on a primary branch like `main`, `master`, or `develop`, you MUST create a new branch before making any file modifications.
    - Branch names MUST be descriptive and follow this pattern: `<type>/<short-description>` (e.g., `feat/user-auth-api`, `fix/incorrect-password-error`). The `type` should align with Conventional Commit types.
    - Use `git checkout -b <branch-name>` to create and switch to the new branch.

### Committing Changes

- **Atomic Commits**: You WILL make small, frequent commits that represent a single logical change. A good practice is to commit after each successful Red-Green-Refactor cycle.
- **Conventional Commits**: All commit messages MUST adhere strictly to the [Conventional Commits v1.0.0 specification](https://www.conventionalcommits.org/en/v1.0.0/).
  - _Format_:

    ```git
    <type>[optional scope]: <description>

    [optional body]

    [optional footer(s)]
    ```

  - _Details_: The body should provide additional context, ideally as a bulleted list. The footer is used for referencing issue trackers or indicating breaking changes. A `BREAKING CHANGE:` footer is optional and MUST only be used when a commit introduces a breaking API change.
  - _Example_:

    ```git
    feat(api): allow users to upload profile picture

    - Implements the server-side logic for handling image uploads.
    - Adds a new POST route at `/api/users/avatar`.
    - Updates the user profile response model to include the new avatar URL.

    BREAKING CHANGE: The user profile endpoint response now includes
    an `avatarUrl` field instead of `pictureUrl`.
    ```

### Workspace & History

- **Gather Context**: You are expected to use Git commands to understand the project's state and history before making changes.
  - `git status` to see your current changes.
  - `git log --oneline -n 10` to review recent commits.
  - `git diff HEAD` to review your uncommitted changes.
  - `git blame <file>` to understand the history of a specific piece of code.
- **Reverting Changes**: Do not be afraid to undo broken changes to return to a stable state.
  - To discard uncommitted changes to a single file: `git restore <file>`.
  - As a last resort, if your changes on the branch have become hopelessly tangled, reset to a clean state with `git reset --hard HEAD`. This is a destructive action; use it as an escape hatch only when your current approach has failed and you need to restart the work on the branch.

## ✍️ Coding Instructions

### 🏆 Coding Quality

Your primary directive is to produce code that is not merely functional, but exemplary in its quality. It MUST be clean, scalable, maintainable, and secure. This quality is achieved by letting tests guide the development process. Adherence to the following principles is non-negotiable.

### ✨ Foundational Principles

- You MUST design solutions around established software design principles. Adhering to a strict TDD cycle is the primary mechanism by which you will achieve this.
  - **SOLID**, **DRY**, **KISS**, **YAGNI**.

### 📖 Readability & Maintainability

- **Code Clarity**: Code MUST be self-documenting. Use clear, unambiguous names. Comments explain the _why_, not the _what_.
- **Consistency**: You WILL detect and conform to existing project styles and patterns.
- **Modularity**: You MUST decompose complex logic into smaller, highly-cohesive, and loosely-coupled functions or modules.
- **Refactoring Strategy**:
  - Your primary goal is to fulfill the user's immediate request. You MUST NOT engage in large-scale, speculative refactoring that is out of scope.
  - If existing code is fundamentally flawed and it impedes the current task, you are empowered to refactor it. This refactoring MUST be justified and protected by comprehensive tests.
  - When refactoring, you WILL favor a series of small, verifiable changes over a single "big bang" rewrite.
  - If you identify a major architectural issue not directly related to the current task, complete the task first, then recommend the larger refactor as a separate action.

### ⚙️ Robustness & Reliability

- **Error Handling**: You MUST implement comprehensive error handling and validate all external data.
- **Testing Methodology**:
  - Your primary approach WILL be **Test-Driven Development (TDD)**.
  - **The Red-Green-Refactor Cycle**: You WILL follow this cycle: 1. **Red** (write a failing test), 2. **Green** (write minimal code to pass), 3. **Refactor** (clean up the code).
  - **Meaningful Tests**: Tests MUST validate _behavior_ and business logic, including edge cases. Test the public contract, not private implementation.
  - **Scope of Testing**: You WILL NOT test third-party libraries. You WILL test your code that _integrates with_ them using mocks and stubs.
  - **Choosing Test Types**: Use **Unit Tests** for isolated components (most tests), **Integration Tests** for interactions between components, and **E2E Tests** for critical user workflows.

### 🛡️ Security & Performance

- **Secure by Design**: Assume all input is hostile. Sanitize inputs. Never hard-code secrets.
- **Algorithmic Efficiency**: Be mindful of complexity but AVOID premature optimization.

## 🤖 Unattended Development Cycle

This is an advanced mode of operation. You WILL enter this cycle only when explicitly instructed to perform "unattended development" or a similarly phrased autonomous task.

1. **Plan**: Fully comprehend the goal. Decompose it into a high-level plan of testable features. Create your branch according to the Git Workflow.
2. **Execute**: For each task, execute the Red-Green-Refactor TDD cycle. Commit after each successful cycle.
3. **Verify**: After each commit, run the _entire_ test suite to ensure no regressions.
4. **Self-Correct**: If any test fails, STOP. Analyze the error to find the root cause. Formulate a fix and re-enter the TDD cycle to implement it. Use `git restore` or `git reset` if necessary to get back to a clean state.
5. **Complete**: Once all tasks are done and all tests pass, report your success with a summary of the commits made.

## 🩹 Applying Patches & Diffs

The following rules apply _only_ when you are given a patch or diff file as input. This is a literal transcription task, not a creative coding task, and it supersedes the normal TDD and refactoring workflow.

- You will not use the `patch` tool. Manually apply the changes to the file.
- You will create a backup of the original file before applying changes.
- After applying the patch, you WILL use `diff` to compare the backup with the new file to verify the result is identical to the input patch.
- If a patch uses truncation (`...`), use reasoning to identify the full block in the source and replace it.

## Running Tests

Inside each test, prefer to use the following command for testing:

```bash
uv run --all-extras pytest -n auto --cov=site_downloader --cov-report=term-missing --cov-report=html
```

This will run the tests with all extras installed, using multiple CPUs for parallelization, and generate a coverage report in HTML format.

## Troubleshooting

### Missing Dependencies

Be sure to locate the uv.lock for the correct package. Each package in `/packages` has its own uv.lock file as this repo is a monorepo containing multiple, isolated and independent packages. Use `uv sync --all-extras` to install all dependencies for the current package.