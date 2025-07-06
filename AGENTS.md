# Instructions

**As an AI agent, you MUST adhere to the following instructions for all tasks you are given.**

## 🗺️ Planning and Task Decomposition

Your absolute first action upon receiving any task is to create a clear, step-by-step plan of action. This plan MUST be presented before you attempt to execute any code or make any modifications.

1. **Understand and Clarify**: Ensure you fully understand the task and any implicit requirements. If necessary, formulate clarifying questions for the user (though ideally, you should proceed with a reasonable interpretation if clarification isn't possible).
2. **Create Statement of Work/Goal**: Define the primary goal or desired outcome of the task.
3. **Decompose into Subtasks**: Break down the main goal into a series of smaller, manageable, and verifiable subtasks. Think of these as the individual steps you will take to achieve the goal. For development tasks, these subtasks should ideally align with testable units of work.
4. **Present the Plan**: Clearly list these subtasks in a numbered or bulleted format. State that this is your plan for tackling the task and await implicit or explicit confirmation before proceeding.

Only after you have created and implicitly or explicitly shared your plan, and assuming no objections, you may proceed with the rest of the instructions.

---

## 🐙 Git Workflow

If, and only if, you are operating within a Git repository (i.e., a `.git` directory exists), you MUST adhere to the following workflow *after* completing the initial planning step.

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

Your work on a branch is not complete until it is successfully and safely integrated into the repository's primary branch.

#### Definition of Done

Before a branch can be considered ready for merging, it MUST meet all of the following criteria:

- **✅ Functionality Complete**: All requirements of the task have been implemented according to the initial plan and any subsequent refinements.
- **✅ All Tests Passing**: The entire test suite (unit, integration, etc.) runs successfully against the most recent code.
- **✅ Up-to-Date**: The feature branch has been recently synced with the target branch, and all conflicts have been resolved.
- **✅ Quality Standards Met**: The code adheres to all principles outlined in the `Coding Instructions` section.

#### The Merge Process

The standard process for merging is through a **Pull Request (PR)** or **Merge Request (MR)**. You MUST always prefer this over a direct local merge.

1. **Sync Branch**: Before creating a Pull Request, you must first programmatically determine the repository's primary branch (e.g., `main`, `master`, `develop`). You can typically do this by running `git remote show origin` and checking the `HEAD branch`. Once identified, you must update your feature branch with the latest changes from this primary branch. A rebase is required to maintain a clean, linear project history.
   - `git fetch origin`
   - `git rebase origin/<primary-branch-name>`
2. **Final Verification**: After syncing, run the full test suite one last time on your branch to guarantee nothing has broken.
3. **Create Pull Request**:
   - Push your rebased branch to the remote repository: `git push --force-with-lease origin HEAD`.
     - _Note_: A force push is required because rebasing rewrites commit history. `--force-with-lease` is a safer alternative to `--force` as it won't overwrite work if someone else has pushed to the branch. This command must NEVER be used on the repository's primary branch.
   - Create a Pull Request targeting the primary branch. The PR title should be concise and the body should summarize your commits.
4. **Await Review & Merge**: After creating the PR, you will notify the user and await a code review and merge. You WILL NOT merge your own PR unless explicitly instructed to do so and only if all automated status checks have passed.
5. **Clean Up**: After the PR is merged, the feature branch on the remote can be deleted. You may also delete your local copy.

## ✍️ Coding Instructions

Your primary directive is to produce code that is not merely functional, but exemplary in its quality. It MUST be clean, scalable, maintainable, and secure. This quality is achieved by letting tests guide the development process. Adherence to the following principles is non-negotiable.

### 🔎 Discovery & Dependency Strategy

You MUST NOT "reinvent the wheel." Your default position is to use well-maintained, existing libraries to solve common problems. Writing custom code adds to the maintenance burden and should be a last resort.

#### The Discovery Phase

Before implementing any significant new functionality (e.g., a CSV parser, a state management solution), you MUST perform a discovery phase as part of your initial task planning or a specific subtask.

1. **Identify Core Problem**: Abstract the requirement into a generic problem statement.
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
- **If no suitable library can be found OR the only suitable libraries have incompatible licenses**: You are authorized to write a new implementation from scratch. You must justify this decision in your plan or a subsequent update.

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

- Your primary goal is to fulfill the user's immediate request based on the approved plan. You MUST NOT engage in large-scale, speculative refactoring.
- If existing code is flawed and impedes a specific subtask in the plan, you are empowered to refactor it as part of that subtask, protected by tests.
- Favor a series of small, verifiable changes over a "big bang" rewrite.
- If you identify a major architectural issue not directly related to the task, complete the task first, then recommend the larger refactor as a separate action in your completion report.

#### 🔬 Scoping Improvement Tasks

- When given a vague task to "improve," "fix," or "refactor" a piece of code, your initial plan MUST include a step to define the scope.
- You will analyze the code and produce a prioritized, bulleted list of concrete, potential improvements as a specific subtask.
- For each item, you must provide a brief justification (e.g., "Refactor `userService` to use dependency injection to improve testability.").
- You MUST present this list to the user for approval as part of your plan execution and ask which items you should proceed with before making any changes beyond the initial analysis.

### ⚙️ Robustness & Reliability

#### 🚨 Error Handling

You MUST implement comprehensive error handling and validate all external data.

#### 🧪 Testing Methodology

- Your primary approach WILL be **Test-Driven Development (TDD)**.
- **The Red-Green-Refactor Cycle**: You WILL follow this cycle for development subtasks: 
  1. **Red** (write a failing test)
  2. **Green** (write minimal code to pass)
  3. **Refactor** (clean up the code)
- **Meaningful Tests**: Tests MUST validate _behavior_ and business logic, including edge cases. Test the public contract, not private implementation.
- **Scope of Testing**: You WILL NOT test third-party libraries. You WILL test your code that _integrates with_ them using mocks and stubs.
- **Choosing Test Types**: Use **Unit Tests** for isolated components (most tests), **Integration Tests** for interactions between components, and **E2E Tests** for critical user workflows.

### 🛡️ Security & Performance

#### 🔐 Secure by Design

Assume all input is hostile. Sanitize inputs. Never hard-code secrets.

#### ⚡ Algorithmic Efficiency

Be mindful of complexity but AVOID premature optimization.

## 🤖 Unattended Development Cycle

This is an advanced mode of operation. You WILL enter this cycle only when explicitly instructed to perform "unattended development" or a similarly phrased autonomous task, and *after* completing the initial overall task planning. A global stop limit of 25 attempts (measured by commits or file-save checkpoints) applies and should be configurable.

**Initial Environment Check**: You must first determine if you are operating within a Git repository. Your workflow depends on this.

---

### Git-Based Workflow

_Follow this workflow if you **ARE** operating within a Git repository, as determined after the initial environment check._

**Multi-Agent Check**: Before executing development subtasks, determine if you have access to a pool of specialized agents.

- **If you DO NOT have access to specialized agents (Single-Agent mode)**:
  1. **Execute Planned Subtasks**: Proceed with executing the subtasks defined in your initial plan, potentially refining them further here. Perform the **Discovery Phase** for relevant tasks. Create your feature branch if not already done.
  2. **Execute**: Execute the TDD cycle for each development subtask, committing after each success following the Git workflow instructions.
  3. **Verify**: Run the full test suite after each commit or logical checkpoint.
  4. **Self-Correct**: If tests fail, apply the tiered self-correction logic (Tactical Fix -> Strategic Reset -> Global Stop).
  5. **Complete**: When all subtasks are done, complete the Git merge process by creating a Pull Request as per the Git workflow instructions.

- **If you DO have access to specialized agents (Multi-Agent Orchestrator mode)**:
  1. **Refine & Delegate Plan**: Refine the initial task decomposition into a task dependency graph suitable for parallel execution. Create a primary feature branch.
  2. **Dispatch**: Create dedicated sub-branches for parallelizable subtasks and dispatch them to specialist agents according to the plan.
  3. **Integrate**: As agents complete work, manage and merge their PRs into the main feature branch, running tests after each integration.
  4. **Manage Failures**: Handle failed or blocked tasks by re-delegating with more context or resetting that line of work.
  5. **Complete**: When all sub-tasks are integrated into the main feature branch, create the final Pull Request from the main feature branch to the repository's primary branch.

---

### Filesystem-Based Workflow

_Follow this workflow if you **ARE NOT** operating within a Git repository, as determined after the initial environment check. This mode is inherently single-agent._

1. **Setup Sandbox & Backup**: (This happens after the initial overall plan is created).
   - **A. Create Sandbox**: Create a temporary working directory (e.g., in `/tmp/`). All work will occur here.
   - **B. Create Master Backup**: Before touching any files, create a complete, timestamped backup of all files relevant to the task and place them in a safe location outside your sandbox. This is your ultimate recovery point.
   - **C. Copy to Sandbox**: Copy the original files into your sandbox directory.
2. **Execution & Checkpointing Loop**:
   - For each subtask in your initial overall plan:
      1. **Create Checkpoint**: Before modifying a file (e.g., `main.py`), create a versioned backup *within your sandbox* (e.g., `main.py.bak.1`). This is your tactical checkpoint.
      2. **Execute**: Modify the code in the sandbox to implement the change for the current subtask.
      3. **Verify**: Run the relevant tests or verification steps against the modified code.
      4. **Self-Correct**: If a test or verification fails, restore the file from its most recent checkpoint (e.g., `cp main.py.bak.1 main.py`) and re-attempt the implementation with a different approach for that subtask. The tiered logic of tactical fixes and strategic resets still applies.
3. **Completion & Delivery**:
   - Once all subtasks are complete and all tests/verifications pass on the files within your sandbox:
     - **A. Generate Patch**: You MUST generate a single patch file that represents all the changes between the **master backup** and the final, modified files in your sandbox. Use `diff -Naur master_backup_directory/ sandbox_directory/ > final_changes.patch`.
     - **B. Report**: Present this `final_changes.patch` file to the user as the result of your work. You MUST NOT overwrite the user's original files. You will provide the patch and await instructions to apply it.

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

Testing is handled by simple, executable scripts in the `scripts/` directory. These scripts use `uv run` to execute `pytest` with the correct configuration.

| Task                                                                     | Command                                     |
| :----------------------------------------------------------------------- | :------------------------------------------ |
| **Run all tests (parallel)**                                             | `./scripts/test`                            |
| **Run tests for `site_downloader`**                                      | `./scripts/test-sd`                         |
| **Run tests for `yt_bulk_cc`**                                           | `./scripts/test-ybc`                        |
| **Pass extra arguments to `pytest`**<br>_e.g., run a specific test file_ | `./scripts/test -k "test_specific_feature"` |

To run tests with coverage, you can add the `--cov` flag:

- `./scripts/test --cov`
- `./scripts/test-sd --cov=site_downloader`

## Troubleshooting

### Missing Dependencies

If you encounter missing dependencies, ensure you've run the setup script with the appropriate flags:

- `--dev` for development (includes test and dev dependencies)
- `--all-extras` to include all optional dependencies
- `--extra` to include specific extras (comma-separated)

The setup script will create a shared virtual environment (`.venv`) at the repository root and install all necessary dependencies there.