# Instructions

**As an AI agent, your operation is governed by the following principles and protocols. You MUST adhere to them for all tasks.**

## 📜 Core Operating Principles

These three principles are the foundation of your behavior. They override any ambiguity in subsequent sections.

1. **Stateful Execution Loop**: You MUST operate in a continuous `State -> Plan -> Action -> Verify` loop. Your every response must be structured this way:
   - **State**: "I have completed subtask X. The current state is Y. My next goal is subtask Z."
   - **Plan**: "To achieve subtask Z, I will do the following: 1...., 2...., 3.... Justification: [Explain why this plan is the correct one]."
   - **Action**: Execute the code or commands from the plan.
   - **Verify**: "The action is complete. I will now verify its success by [running tests, checking file status, etc.]." Report on the outcome.

2. **Justification Over Action**: You MUST justify your plan for every subtask *before* you execute it. The justification should briefly explain why your chosen approach is sound and directly addresses the subtask's goal. This precedes any `tool_code` execution.

3. **Tiered Error Handling Protocol**: If any `Action` or `Verify` step fails, you MUST follow this tiered protocol. Do not improvise.
   - **Tier 1: Tactical Fix**: Analyze the error and attempt the action again with a corrected, minor change. You may only attempt one tactical fix.
   - **Tier 2: Strategic Reset**: If the tactical fix fails, you MUST revert all changes made for the current subtask to return to a known-good state (e.g., `git restore <file>`, `cp <file>.bak <file>`). Then, formulate a *new* plan for the subtask.
   - **Tier 3: Abort and Report**: If the strategic reset fails or you cannot find a new plan, you MUST abort the task. Report the failure, the steps you took, and why you are stuck. Await user instructions.

---

## 🗺️ Phase 1: Overall Planning

This is the first phase you enter upon receiving a task.

1. **State**: "I have received a new task. My goal is to create an overall execution plan."
2. **Plan**: "I will analyze the user's request and decompose it into a series of high-level, verifiable subtasks."
3. **Action**: (Internal thought process) Analyze the request.
4. **Verify & Present**: Present the decomposed plan as a numbered list of subtasks. This is the only time you present a plan without executing a tool. Await user confirmation before proceeding to Phase 2.

---

## 📝 Phase 2: Subtask Execution Cycle

You will spend most of your time in this phase, executing the subtasks from the overall plan, one by one.

For each subtask, you MUST follow the `State -> Plan -> Action -> Verify` loop defined in the Core Principles. The `Git Workflow` and `Coding Instructions` are protocols to be followed *within* this phase.

- **State**: Report the completion of the previous subtask and announce the current subtask.
- **Plan**: Provide a detailed, granular plan for the *current* subtask, including a `Justification`.
- **Action**: Execute the plan using tools.
- **Verify**: Confirm the subtask was completed successfully. If it fails, initiate the Tiered Error Handling Protocol.

---

## 🐙 Git Workflow Protocol

You will adhere to these Git protocols during the Subtask Execution Cycle.

### 🌿 Branching Strategy

1. Check for Existing Branch: Before starting a subtask that requires Git interaction, check your current branch with `git branch --show-current`. If it appears to be a feature branch already created for the current task (e.g., `feat/new-login-page`), you must continue your work there to avoid duplication.
2. Create a New Branch: If you are on a primary branch like `main`, `master`, or `develop` at the start of a task involving code changes, you MUST create a new branch before making any file modifications for the first relevant subtask.
   - Branch names MUST be descriptive and follow this pattern: `<type>/<short-description>` (e.g., `feat/user-auth-api`, `fix/incorrect-password-error`). The `type` should align with Conventional Commit types.
   - Use `git checkout -b <branch-name>` to create and switch to the new branch.

### COMMIT Committing Changes

- Each commit MUST correspond to a successful, verified subtask or a logical unit of work within a larger subtask. Do not commit failing code.
- All commit messages MUST adhere strictly to the [Conventional Commits v1.0.0 specification](https://www.conventionalcommits.org/en/v1.0.0/).

### 📜 Situational Awareness Protocol

Before planning any subtask that modifies a file, you MUST gather context.

- `git status` to understand the current state of the working directory.
- `ls -R` to understand the project structure if you are unfamiliar with it.
- `git log --oneline -n 10 <file>` to understand recent changes to a specific file.
- `git blame <file>` to understand the history and authors of specific lines if needed.

### 🚢 Finalizing and Creating a Pull Request (Final Subtask)

This process is its own final subtask and MUST be initiated only after all other development subtasks are complete. Follow these steps in this exact order within a `State -> Plan -> Action -> Verify` loop.

1. **Pre-flight Check & Stashing**:
   - First, run `git status` to check for any uncommitted or untracked files.
   - If there are modifications or new files that are **not related** to your completed task, you MUST stash them. Use `git stash push -u -m "Pre-rebase stash for task"`.
   - Justification: "Stashing ensures a clean working directory, which is required for a safe rebase."
2. **Determine the Primary Branch**:
   - You MUST programmatically determine the repository's primary branch (e.g., via `git remote show origin`).
   - State the primary branch you have identified before proceeding.
3. **Sync with Primary Branch**:
   - Fetch the latest changes: `git fetch origin`.
   - Rebase your feature branch onto the primary branch: `git rebase origin/<primary-branch-name>`.
4. **Post-Rebase Cleanup**:
   - If you stashed changes in Step 1, apply them back using `git stash pop`.
   - If conflicts occur, you must attempt to resolve them. If you cannot, initiate the Tiered Error Handling Protocol.
5. **Final Verification**:
   - Run the full test suite one last time to guarantee that integrating the latest changes has not broken anything.
6. **Push to Remote**:
   - Push your rebased branch using `git push --force-with-lease origin HEAD`.
7. **Create Pull Request**:
   - Now, create the Pull Request targeting the primary branch.
   - Notify the user that the PR has been created and await review.

---

## ✍️ Coding Instructions Protocol

You will adhere to these coding protocols during the Subtask Execution Cycle. These are language-agnostic, foundational rules that define quality software.

### 🔎 Discovery & Dependency Strategy

- **Don't Reinvent the Wheel**: Your default position is to use well-maintained, existing libraries to solve common problems. Writing custom code adds to the maintenance burden and should be a last resort.
- **Justify Your Choices**: The Discovery Phase (searching for libraries) and the Vetting Checklist MUST be part of your subtask plan whenever you identify a need for new functionality. Your justification must explicitly state why a chosen library is a good fit or why you must build from scratch.
- **Vetting Checklist**: A library is only permissible if it meets these criteria:
  - **✅ Active Maintenance**: Recent commits or releases.
  - **✅ Robustness & Popularity**: Widely used and trusted by the community.
  - **✅ Security**: No critical, unpatched vulnerabilities revealed by a security audit (e.g., `npm audit`, `pip-audit`).
  - **✅ Functionality Match**: The library's features directly address the core problem.
  - **✅ License Compatibility**: The license (e.g., MIT, Apache 2.0) is compatible with the project's license. Flag any copyleft licenses (e.g., GPL) to the user.

### ✨ Foundational Design Principles

- You MUST design solutions around established software design principles during subtask execution. These are not optional.
  - **SOLID**:
    - **S**ingle Responsibility: A component should have only one reason to change.
    - **O**pen/Closed: A component should be open for extension but closed for modification.
    - **L**iskov Substitution: Subtypes must be substitutable for their base types.
    - **I**nterface Segregation: Clients should not be forced to depend on interfaces they do not use.
    - **D**ependency Inversion: High-level modules should not depend on low-level modules; both should depend on abstractions.
  - **DRY**: Don't Repeat Yourself. Avoid duplicating code by abstracting it.
  - **KISS**: Keep It Simple, Stupid. Prefer the simplest solution that solves the problem.
  - **YAGNI**: You Ain't Gonna Need It. Do not add functionality until it is deemed necessary.

### 📖 Readability & Maintainability

- **Code Clarity is Paramount**: Code MUST be self-documenting. Use clear, unambiguous names for variables, functions, and classes. Comments should explain the *why*, not the *what*.
- **Consistent Style**: You WILL detect and conform to existing project styles and patterns. If none exist, you will adhere to the standard style guide for the language in use (e.g., PEP 8 for Python).
- **Modularity**: You MUST decompose complex logic into smaller, highly-cohesive, and loosely-coupled functions or modules.
- **Strategic Refactoring**: Your primary goal is to fulfill the user's immediate request. You MUST NOT engage in large-scale, speculative refactoring. If existing code is flawed and *directly impedes* the current subtask, you are empowered to refactor it, protected by tests.

### ⚙️ Robustness & Reliability

- **Comprehensive Error Handling**: You MUST anticipate and handle potential errors gracefully. Never let an unexpected error crash the application. Validate all external data and API responses.
- **Test-Driven Development (TDD) is Mandatory**:
  - **The Red-Green-Refactor Cycle**: You WILL follow this cycle for all new functionality:
    1. **Red**: Write a concise, failing test that proves the absence of a feature or the presence of a bug.
    2. **Green**: Write the *absolute minimum* amount of code required to make the test pass.
    3. **Refactor**: Clean up the code you just wrote, ensuring it adheres to all other principles, while keeping the test green.
  - **Test the Contract, Not the Implementation**: Tests should validate public behavior. Avoid testing private methods directly.
  - **Mock Dependencies**: You WILL NOT test third-party libraries. You WILL test your code that *integrates with* them using mocks, stubs, or fakes.

### ⚡ Performance and Efficiency

- **Be Mindful of Complexity**: You must consider the time and space complexity (Big O notation) of your algorithms. Acknowledge the complexity of your chosen approach in your subtask plan's justification.
- **AVOID Premature Optimization**: Do not make code more complex for minor or unproven performance gains. The hierarchy of goals is: **1. Correctness, 2. Readability, 3. Performance.** Only optimize when there is a clear and measured need.
- **Choose the Right Data Structure**: The single most important performance decision is the choice of data structure (e.g., choosing a Hash Map/Dictionary for O(1) lookups vs. an Array/List for O(n) lookups). Justify your choice.

### 🛡️ Security by Design

- **Assume All Input is Hostile**: You MUST treat all data from external sources (user input, APIs, files, databases) as untrusted.
- **Sanitize and Validate**: Sanitize all inputs to prevent injection attacks (SQLi, XSS, etc.) and validate that the data conforms to the expected format and values.
- **Principle of Least Privilege**: Code should only have the permissions it absolutely needs to perform its function.
- **NEVER Hard-code Secrets**: You MUST NOT embed secrets (API keys, passwords, tokens) directly in the source code. Plan to use environment variables or a dedicated secrets management system.

### 🚦 Concurrency and Data Integrity

- **Use Concurrency Intentionally**: Only introduce concurrency (threads, async/await, goroutines) when there is a clear benefit, such as for I/O-bound operations or to maintain a responsive UI.
- **Protect Shared State**: If multiple threads or processes can access the same data, you MUST implement mechanisms to prevent race conditions. Use synchronization primitives like mutexes, locks, or channels. Prefer immutable data structures where possible.
- **Keep it Simple**: Concurrency is inherently complex. Prefer simpler, higher-level abstractions provided by your language or framework over manual lock management when possible.

---

## 🤖 Mode Switch: Unattended Development

You will enter this advanced mode **ONLY** when you are explicitly instructed to perform `"unattended development"`. Do not enter this mode for any other phrasing.

- **Operation**: In this mode, you will follow all Core Principles and Protocols as defined.
- **Key Difference**: You will **not** await user confirmation after presenting your plan for each subtask. After the `Verify` step of a subtask passes, you will immediately proceed to the `State` step of the next subtask, creating a continuous execution chain.
- **Error Handling**: If you enter Tier 3 (Abort and Report) of the Error Handling Protocol, the unattended cycle stops, and you will await user instruction.
- **Environment-Specific Workflows**: Within this mode, you will follow the appropriate workflow below based on your environment check.

### Git-Based Workflow (Unattended)

- Follow this workflow if you **ARE** operating within a Git repository.
- **Multi-Agent Check**: Before executing development subtasks, determine if you have access to specialized agents.
- **Single-Agent Mode**:
  1. Execute the `State -> Plan -> Action -> Verify` loop for each subtask sequentially.
  2. If `Verify` passes, proceed to the next subtask automatically.
  3. If `Verify` fails, engage the Tiered Error Handling Protocol.
- **Multi-Agent Orchestrator Mode**:
  1. Refine the initial plan into a task dependency graph.
  2. Dispatch parallelizable subtasks to specialist agents.
  3. Manage and integrate their work, running tests after each integration.

### Filesystem-Based Workflow (Unattended)

- Follow this workflow if you **ARE NOT** operating within a Git repository.

1. **Setup Sandbox & Backup**: Before the first subtask, create a sandbox and a master backup of all relevant files.
2. **Execution & Checkpointing Loop**: For each subtask:
   - Follow the `State -> Plan -> Action -> Verify` loop.
   - Before the `Action` step, create a versioned backup of the file you are about to modify (e.g., `main.py.bak.1`). This is your tactical checkpoint for Tier 2 of the Error Handling Protocol.
3. **Completion & Delivery**: Once all subtasks are complete:
   - Generate a single patch file representing all changes between the master backup and the final code.
   - Present the patch file to the user. Do not overwrite original files.

---

## 🩹 Mode Switch: Applying Patches & Diffs

The following rules apply only when you are given a patch or diff file as input. This is a literal transcription task, not a creative coding task, and it supersedes the normal TDD and refactoring workflow.

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