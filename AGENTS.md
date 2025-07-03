# Instructions

## 🐙 Git Workflow

If, and only if, you are operating within a Git repository (i.e., a `.git` directory exists), you MUST adhere to the following workflow. Your first action upon receiving a task should be to verify this condition and act accordingly.

### 🌿 Branching Strategy

1. **Check for Existing Branch**: Before starting, check your current branch with `git branch --show-current`. If it appears to be a feature branch already created for the current task (e.g., `feat/new-login-page`), you must continue your work there to avoid duplication.
2. **Create a New Branch**: If you are on a primary branch like `main`, `master`, or `develop`, you MUST create a new branch before making any file modifications.
    - Branch names MUST be descriptive and follow this pattern: `<type>/<short-description>` (e.g., `feat/user-auth-api`, `fix/incorrect-password-error`). The `type` should align with Conventional Commit types.
    - Use `git checkout -b <branch-name>` to create and switch to the new branch.

### COMMIT Committing Changes

- **Atomic Commits & Checkpoints**: You WILL make small, frequent commits that represent a single logical unit of work. This practice is non-negotiable as it creates a detailed history and provides safe, granular checkpoints to revert to. After completing a unit of work, you MUST stage the relevant changes using `git add <file>...` before creating the commit with `git commit`. A commit should be made after each successful Red-Green-Refactor cycle.
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

### 📜 Workspace & History

- **Gather Context**: You are expected to use Git commands to understand the project's state and history before making changes.
    - `git status` to see your current changes.
    - `git log --oneline -n 10` to review recent commits.
    - `git diff HEAD` to review your uncommitted changes.
    - `git blame <file>` to understand the history of a specific piece of code.
- **Reverting Changes**: Do not be afraid to undo broken changes to return to a stable state.
    - To discard uncommitted changes to a single file: `git restore <file>`.
    - As a last resort, if your changes on the branch have become hopelessly tangled, reset to a clean state with `git reset --hard HEAD`. This is a destructive action; use it as an escape hatch only when your current approach has failed and you need to restart the work on the branch.

### 🚢 Merging & Completion

Your work on a branch is not complete until it is successfully and safely integrated into the primary branch (`main`, `develop`).

#### Definition of Done

Before a branch can be considered ready for merging, it MUST meet all of the following criteria:

- **✅ Functionality Complete**: All requirements of the task have been implemented.
- **✅ All Tests Passing**: The entire test suite (unit, integration, etc.) runs successfully against the most recent code.
- **✅ Up-to-Date**: The feature branch has been recently synced with the target branch (e.g., `main`), and all conflicts have been resolved.
- **✅ Quality Standards Met**: The code adheres to all principles outlined in the `Coding Instructions` section.

#### The Merge Process

The standard process for merging is through a **Pull Request (PR)** or **Merge Request (MR)**. You MUST always prefer this over a direct local merge.

1. **Sync Branch**: Before creating a Pull Request, you must update your feature branch with the latest changes from the target branch (e.g., `main`). This ensures your changes work with the most recent version of the codebase. A rebase is required to maintain a clean, linear project history.
    - `git fetch origin`
    - `git rebase origin/main` (replace `main` with the correct target branch)
2. **Final Verification**: After syncing, run the full test suite one last time on your branch to guarantee nothing has broken.
3. **Create Pull Request**:
    - Push your rebased branch to the remote repository: `git push --force-with-lease origin HEAD`.
      - _Note_: A force push is required because rebasing rewrites commit history. `--force-with-lease` is a safer alternative to `--force` as it won't overwrite work if someone else has pushed to the branch. This command must NEVER be used on `main` or `develop`.
    - Create a Pull Request targeting the primary branch. The PR title should be concise and the body should summarize your commits.
4. **Await Review & Merge**: After creating the PR, you will notify the user and await a code review and merge. You WILL NOT merge your own PR unless explicitly instructed to do so and only if all automated status checks have passed.
5. **Clean Up**: After the PR is merged, the feature branch on the remote can be deleted. You may also delete your local copy.

## ✍️ Coding Instructions

### 🏆 Coding Quality

Your primary directive is to produce code that is not merely functional, but exemplary in its quality. It MUST be clean, scalable, maintainable, and secure. This quality is achieved by letting tests guide the development process. Adherence to the following principles is non-negotiable.

### 🔎 Discovery & Dependency Strategy

You MUST NOT "reinvent the wheel." Your default position is to use well-maintained, existing libraries to solve common problems. Writing custom code adds to the maintenance burden and should be a last resort.

#### The Discovery Phase

Before implementing any significant new functionality (e.g., a CSV parser, a state management solution), you MUST perform a discovery phase.

1. **Identify Core Problem**: Abstract the request into a generic problem statement.
2. **Search for Solutions**: Search relevant package registries (e.g., npm, PyPI, Maven Central) for existing libraries that solve this problem.

#### Vetting Checklist

You are only permitted to use a third-party library if it meets ALL of the following criteria. You must explicitly verify each point.

- **✅ Active Maintenance**: The project shows recent activity (e.g., commits/releases within the last 6-12 months).
- **✅ Robustness & Popularity**: The library is widely used and trusted by the community (e.g., significant download counts, stars).
- **✅ Security**: A security audit (e.g., `npm audit`) reveals no critical, unpatched vulnerabilities.
- **✅ Functionality Match**: The library's features directly address the core problem.
- **✅ License Compatibility**: The library's license (e.g., MIT, Apache 2.0) is compatible with the project's license. You MUST flag any copyleft licenses (e.g., GPL, AGPL) to the user, as they may be incompatible.

#### Implementation Decision

- **If a library passes all checks**: Add it as a project dependency. Your task is now to integrate this library.
- **If a library passes all checks but only partially solves the problem**: Create a "wrapper" or "adapter" module that uses the library and adds the missing functionality. Do not replicate its features.
- **If no suitable library can be found OR the only suitable libraries have incompatible licenses**: You are authorized to write a new implementation from scratch. You must justify this decision.

### ✨ Foundational Principles

You MUST design solutions around established software design principles. Adhering to a strict TDD cycle is the primary mechanism by which you will achieve this.

- **SOLID**: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.
- **DRY**: Don't Repeat Yourself.
- **KISS**: Keep It Simple, Stupid.
- **YAGNI**: You Ain't Gonna Need It.

### 📖 Readability & Maintainability

#### 💡 Code Clarity

Code MUST be self-documenting. Use clear, unambiguous names. Comments explain the _why_, not the _what_.

#### 🎨 Consistency

You WILL detect and conform to existing project styles and patterns.

#### 🧱 Modularity

You MUST decompose complex logic into smaller, highly-cohesive, and loosely-coupled functions or modules.

#### 🛠️ Refactoring Strategy

- Your primary goal is to fulfill the user's immediate request. You MUST NOT engage in large-scale, speculative refactoring.
- If existing code is flawed and impedes the task, you are empowered to refactor it, protected by tests.
- Favor a series of small, verifiable changes over a "big bang" rewrite.
- If you identify a major architectural issue not directly related to the task, complete the task first, then recommend the larger refactor as a separate action.

### ⚙️ Robustness & Reliability

#### 🚨 Error Handling

You MUST implement comprehensive error handling and validate all external data.

#### 🧪 Testing Methodology

- Your primary approach WILL be **Test-Driven Development (TDD)**.
- **The Red-Green-Refactor Cycle**: You WILL follow this cycle: 1. **Red** (write a failing test), 2. **Green** (write minimal code to pass), 3. **Refactor** (clean up the code).
- **Meaningful Tests**: Tests MUST validate _behavior_ and business logic, including edge cases. Test the public contract, not private implementation.
- **Scope of Testing**: You WILL NOT test third-party libraries. You WILL test your code that _integrates with_ them using mocks and stubs.
- **Choosing Test Types**: Use **Unit Tests** for isolated components (most tests), **Integration Tests** for interactions between components, and **E2E Tests** for critical user workflows.

### 🛡️ Security & Performance

#### 🔐 Secure by Design

Assume all input is hostile. Sanitize inputs. Never hard-code secrets.

#### ⚡ Algorithmic Efficiency

Be mindful of complexity but AVOID premature optimization.

## 🤖 Unattended Development Cycle

This is an advanced mode of operation. You WILL enter this cycle only when explicitly instructed to perform "unattended development" or a similarly phrased autonomous task.

1. **Clarify & Plan**:
    - **A. Clarify Goal**: First, restate the user's request in your own words as a clear "Statement of Work." This statement MUST include a bulleted list of specific, verifiable acceptance criteria. If the request is ambiguous, you MUST ask clarifying questions before proceeding.
    - **B. Create Plan**: Once the goal is clear, decompose it into a high-level plan of testable features or tasks. For each feature, you MUST first perform the **Discovery Phase** as defined in the `Discovery & Dependency Strategy` section.
    - **C. Setup Branch**: After the plan is finalized, create your branch according to the Git Workflow.

2. **Execute**: For each task in your plan, execute the TDD cycle. This may involve integrating a library or writing new code from scratch, based on the outcome of your Discovery Phase. Commit after each successful cycle.

3. **Verify**: After each commit, run the _entire_ test suite to ensure no regressions were introduced.

4. **Verify & Self-Correct**: After each commit, run the _entire_ test suite.
    - **If all tests pass**: Proceed to the next task in your plan.
    - **If any test fails**: You will enter the following tiered self-correction process.
        - **Tier 1: Tactical Fix (Up to 3 attempts)**
            1. **Analyze**: Examine the error and the last commit to form a hypothesis on the root cause.
            2. **Attempt Fix**: Re-enter the TDD cycle to write a specific test for the bug and implement a fix with a new commit.
            3. If the fix also fails, repeat this tactical analysis and fix attempt up to two more times with variations on the implementation.
        - **Tier 2: Strategic Reset**
            1. **If all tactical fixes in Tier 1 fail**, your implementation strategy for the feature is likely flawed.
            2. **Revert**: Reset the branch to the last known good commit (`git reset --hard <sha>`) to discard the entire failed approach for the current feature.
            3. **Re-Plan**: Go back to the planning stage *for this specific feature*. Re-read the requirements and source code, and devise a completely new implementation strategy. Then, begin executing that new strategy from Step 2.
        - **Tier 3: Global Stop**
            1. If you have made 25 attempts (measured by total commits for the task) and the overall goal is still not complete, you MUST stop. This limit should be configurable.
            2. This indicates the task is more complex than anticipated or you are in an unrecoverable loop.
            3. You will then create a Pull Request with your last stable work and report your full progress, the block you encountered, the different strategies you attempted, and why you believe they failed.

5. **Complete**: Once all tasks are done and all tests pass, follow the `Merging & Completion` workflow to create a Pull Request.

## 🩹 Applying Patches & Diffs

The following rules apply _only_ when you are given a patch or diff file as input. This is a literal transcription task, not a creative coding task, and it supersedes the normal TDD and refactoring workflow.

- You will not use the `patch` tool. Manually apply the changes to the file.
- You will create a backup of the original file before applying changes.
- After applying the patch, you WILL use `diff` to compare the backup with the new file to verify the result is identical to the input patch.
- If a patch uses truncation (`...`), use reasoning to identify the full block in the source and replace it.

## Environment Setup

This repository uses a centralized setup script to manage dependencies. To set up the development environment (from project root):

```bash
# Install all packages with development dependencies
./scripts/setup.sh --dev

# Or for production use (minimal dependencies):
# ./scripts/setup.sh --prod
```

## Running Tests

Tests are managed via `uv` scripts defined in the root `pyproject.toml`, providing a simple and consistent interface. These scripts leverage a centralized `pytest` configuration for all packages in the workspace.

### Workspace Commands

These commands operate on all packages within the workspace.

| Task                                                                              | Command           |
| :-------------------------------------------------------------------------------- | :---------------- |
| **Run all tests (sequential)**<br>_Good for debugging._                           | `uv run test`     |
| **Run all tests (parallel)**<br>_Faster; for general use._                        | `uv run test-par` |
| **Run full coverage report (parallel)**<br>_Generates terminal and HTML reports._ | `uv run cov-all`  |

### Package-Specific Commands

For convenience, dedicated aliases exist to test each package individually. This is the recommended way to run tests for a single package.

| Task                                             | Command           |
| :----------------------------------------------- | :---------------- |
| Test `site_downloader` (sequential)              | `uv run test-sd`  |
| Run coverage for `site_downloader` (parallel)    | `uv run cov-sd`   |
| Test `yt_bulk_cc` (sequential)                   | `uv run test-ybc` |
| Run coverage for `yt_bulk_cc` (parallel)         | `uv run cov-ybc`  |

### Execution Modes & Targeting

-   **Sequential vs. Parallel**: For workspace commands, the `-par` suffix runs tests in parallel. For package-specific commands, the `cov-*` scripts run in parallel for speed, while the `test-*` scripts run sequentially for easier debugging.
-   **Targeting Packages**: Using the dedicated aliases (e.g., `uv run test-sd`) is the preferred method for testing a single package.
-   **Coverage Reports**: The `cov-all` command generates a report for the entire workspace. The package-specific `cov-*` aliases generate reports only for that package. All HTML output is located in the root `htmlcov/` directory.

## Troubleshooting

### Missing Dependencies

If you encounter missing dependencies, ensure you've run the setup script with the appropriate flags:

- `--dev` for development (includes test and dev dependencies)
- `--all-extras` to include all optional dependencies
- `--extra` to include specific extras (comma-separated)

The setup script will create a shared virtual environment (`.venv`) at the repository root and install all necessary dependencies there.