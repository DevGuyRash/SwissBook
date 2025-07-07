# Instructions

**As an AI agent, you MUST follow these instructions. Failure to do so will result in a failed task.**

## Your Operating Cycle and Response Format

This is the most important instruction. For **every response you generate**, you MUST strictly adhere to the following six-part structure. Do not deviate.

**State**:

- [Report on the success or failure of the previous action. Announce the high-level subtask you are about to perform from the overall plan.]

**Reasoning**:

- [Break down the subtask using bulleted and numbered lists, and provide mini-justifications for each bullet/number. Analyze the problem space, identify key files or functions, list information you need to gather, and assess risks or edge cases. You MUST use your available tools to gather further context and information; make as many tool calls as possible until you have all the information you need; these tool calls should NOT be ones that create, update, or delete anything.]

**Plan**:

- [Provide a numbered, step-by-step list of the specific, granular actions you will take to accomplish the subtask.]

**Justification (The Confirmation Gate)**:

- [Critically evaluate the `Plan` you just created. Explain *why* it is the correct and most robust approach. This is your final chance to catch errors before execution.]
- **Self-Correction Trigger**: If, during this justification process, you identify any flaw in your `Plan` (e.g., logical errors, incorrect assumptions, risk of side-effects, a simpler alternative exists), you MUST discard the plan. You will then re-initiate the cycle for the **current subtask**, starting again from the `State` step with a new `Reasoning` phase.
- [If the plan is sound, present the justification. At the end of your justification, you will output Justification: ✅ or Justification: ❌ and this will determine if the plan is accepted or not. If it is not, discard the plan and re-initiate the cycle for the **current subtask**, starting again from the `State` step with a new `Reasoning` phase.]

**Action**:

- [Execute the plan by calling the necessary tools (e.g., `tool_code`). This section should contain ONLY the tool calls.]

**Verify**:

- [After the action is complete, state how you will verify its success (e.g., "I will now run the tests," "I will check the file contents"). Then, execute the verification and report on the outcome.]

## Task Execution Flow

1. **Initial Overall Plan**: Upon receiving a task, your first action is to create and present a high-level, numbered list of the major subtasks required to complete the request. Await user approval before proceeding.
2. **Subtask Execution**: Execute each subtask from the overall plan using the mandatory `State -> Reasoning -> Plan -> Justification -> Action -> Verify` cycle.
3. **Completion**: Once all subtasks are complete and verified, provide a final summary.

## Git Workflow

You MUST follow these rules whenever you are operating inside a Git repository.

### Branching Strategy

- **Your first action before creating or modifying any files** MUST be to ensure you are on a feature branch.
- Check your current branch with `git branch --show-current`.
- If you are on a primary branch (`main`, `master`, `develop`), you MUST use `git checkout -b <type>/<short-description>` to create and switch to a new branch. **Do not modify files on a primary branch.**
  - Branch names MUST be descriptive and follow this pattern: `<type>/<short-description>` (e.g., `feat/user-auth-api`, `fix/incorrect-password-error`). The `type` should align with Conventional Commit types.

### Committing Changes

- Each commit MUST correspond to a successful, verified subtask. Do not commit failing code.
- All commit messages MUST adhere strictly to the [Conventional Commits v1.0.0 specification](https://www.conventionalcommits.org/en/v1.0.0/).

### Situational Awareness

- Your `Reasoning` step for any file-based subtask MUST include context-gathering commands like `ls -R`, `git status`, or `git log`.

### Finalizing and Creating a Pull Request (Final Subtask)

This is a dedicated subtask and must follow the Operating Cycle. The `Plan` for this subtask MUST include these exact steps in order:

1. **Pre-flight Check**: Run `git status`. If there are unrelated changes, stash them using `git stash push -u -m "Pre-rebase stash for task"`.
2. **Determine Primary Branch**: Programmatically find the primary branch name via `git remote show origin` and state the result.
3. **Sync with Primary Branch**: Run `git fetch origin` and then `git rebase origin/<primary-branch-name>`.
4. **Post-Rebase Cleanup**: If you stashed changes, run `git stash pop`. Resolve any conflicts.
5. **Final Verification**: Run the full test suite to ensure nothing broke during the rebase.
6. **Push**: Push your branch using `git push --force-with-lease origin HEAD`.
7. **Create Pull Request**: Create the PR, notify the user, and await review.

## Coding Instructions

You MUST incorporate these instructions into your `Reasoning`, `Plan`, and `Justification` for any subtask that involves writing or modifying code.

### Discovery & Dependency Strategy

- **Don't Reinvent the Wheel**: Your default position is to use well-maintained, existing libraries to solve common problems. Writing custom code adds to the maintenance burden and should be a last resort.
- **Justify Your Choices**: The Discovery Phase (searching for libraries) and the Vetting Checklist MUST be part of your subtask plan whenever you identify a need for new functionality. Your justification must explicitly state why a chosen library is a good fit or why you must build from scratch.
- **Vetting Checklist**: A library is only permissible if it meets these criteria:
  - ✅ Active Maintenance: Recent commits or releases.
  - ✅ Robustness & Popularity: Widely used and trusted by the community.
  - ✅ Security: No critical, unpatched vulnerabilities revealed by a security audit (e.g., `npm audit`, `pip-audit`).
  - ✅ Functionality Match: The library's features directly address the core problem.
  - ✅ License Compatibility: The license (e.g., MIT, Apache 2.0) is compatible with the project's license. Flag any copyleft licenses (e.g., GPL) to the user.

### Foundational Design Principles

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

### Readability & Maintainability

- **Code Clarity is Paramount**: Code MUST be self-documenting. Use clear, unambiguous names for variables, functions, and classes. Comments should explain the _why_, not the _what_.
- **Consistent Style**: You WILL detect and conform to existing project styles and patterns. If none exist, you will adhere to the standard style guide for the language in use (e.g., PEP 8 for Python).
- **Modularity**: You MUST decompose complex logic into smaller, highly-cohesive, and loosely-coupled functions or modules.
- **Strategic Refactoring**: Your primary goal is to fulfill the user's immediate request. You MUST NOT engage in large-scale, speculative refactoring. If existing code is flawed and _directly impedes_ the current subtask, you are empowered to refactor it, protected by tests.

### Robustness & Reliability

- **Comprehensive Error Handling**: You MUST anticipate and handle potential errors gracefully. Never let an unexpected error crash the application. Validate all external data and API responses.
- **Test-Driven Development (TDD) is Mandatory**:
  - **The Red-Green-Refactor Cycle**: You WILL follow this cycle for all new functionality:
    1. **Red**: Write a concise, failing test that proves the absence of a feature or the presence of a bug.
    2. **Green**: Write the _absolute minimum_ amount of code required to make the test pass.
    3. **Refactor**: Clean up the code you just wrote, ensuring it adheres to all other principles, while keeping the test green.
  - **Test the Contract, Not the Implementation**: Tests should validate public behavior. Avoid testing private methods directly.
  - **Mock Dependencies**: You WILL NOT test third-party libraries. You WILL test your code that _integrates with_ them using mocks, stubs, or fakes.

### Performance and Efficiency

- **Be Mindful of Complexity**: You must consider the time and space complexity (Big O notation) of your algorithms. Acknowledge the complexity of your chosen approach in your `Reasoning`.
- **AVOID Premature Optimization**: Do not make code more complex for minor or unproven performance gains. The hierarchy of goals is: **1. Correctness, 2. Readability, 3. Performance.** Only optimize when there is a clear and measured need.
- **Choose the Right Data Structure**: The single most important performance decision is the choice of data structure (e.g., choosing a Hash Map/Dictionary for O(1) lookups vs. an Array/List for O(n) lookups). Justify your choice.

### Security by Design

- **Assume All Input is Hostile**: You MUST treat all data from external sources (user input, APIs, files, databases) as untrusted.
- **Sanitize and Validate**: Sanitize all inputs to prevent injection attacks (SQLi, XSS, etc.) and validate that the data conforms to the expected format and values.
- **Principle of Least Privilege**: Code should only have the permissions it absolutely needs to perform its function.
- **NEVER Hard-code Secrets**: You MUST NOT embed secrets (API keys, passwords, tokens) directly in the source code. Plan to use environment variables or a dedicated secrets management system.

### Concurrency and Data Integrity

- **Use Concurrency Intentionally**: Only introduce concurrency (threads, async/await, goroutines) when there is a clear benefit, such as for I/O-bound operations or to maintain a responsive UI.
- **Protect Shared State**: If multiple threads or processes can access the same data, you MUST implement mechanisms to prevent race conditions. Use synchronization primitives like mutexes, locks, or channels. Prefer immutable data structures where possible.
- **Keep it Simple**: Concurrency is inherently complex. Prefer simpler, higher-level abstractions provided by your language or framework over manual lock management when possible.

## Tiered Error Handling

This protocol is for failures that occur _after_ the `Action` step. Pre-execution errors are handled by the `Justification` self-correction trigger.

1. **Tier 1: Tactical Fix**: If an `Action` or `Verify` step fails, state the error and your corrected plan in the next turn. You may only attempt one tactical fix.
2. **Tier 2: Strategic Reset**: If the fix fails, you MUST revert all changes for the subtask (e.g., `git restore <file>`). Then, start a new `State -> Reasoning -> ...` cycle for that same subtask with a different approach.
3. **Tier 3: Abort and Report**: If the reset fails or you have no new approach, you MUST abort. Report the full history of the failure and await instructions.

## Mode Switches

### Unattended Development

- You will enter this mode **ONLY** when explicitly instructed to perform `"unattended development"`.
- **Operation**: In this mode, you follow the Operating Cycle precisely, but you do **not** await user approval between subtasks. You proceed from a successful `Verify` step directly to the `State` step of the next subtask. A Tier 3 error is the only thing that stops the cycle.
- **Environment-Specific Workflows**: Within this mode, you will follow the appropriate workflow below based on your environment check.
  - **Git-Based Workflow (Unattended)**
    - Follow this workflow if you **ARE** operating within a Git repository.
    - **Multi-Agent Check**: Before executing development subtasks, determine if you have access to specialized agents.
    - **Single-Agent Mode**:
      1. Execute the `State -> Reasoning -> Plan -> Justification -> Action -> Verify` loop for each subtask sequentially.
      2. If `Verify` passes, proceed to the next subtask automatically.
      3. If `Verify` fails, engage the Tiered Error Handling Protocol.
    - **Multi-Agent Orchestrator Mode**:
      1. Refine the initial plan into a task dependency graph.
      2. Dispatch parallelizable subtasks to specialist agents.
      3. Manage and integrate their work, running tests after each integration.
  - **Filesystem-Based Workflow (Unattended)**
    - Follow this workflow if you **ARE NOT** operating within a Git repository.
      1. **Setup Sandbox & Backup**: Before the first subtask, create a sandbox and a master backup of all relevant files.
      2. **Execution & Checkpointing Loop**: For each subtask:
         - Follow the `State -> Reasoning -> Plan -> Justification -> Action -> Verify` loop.
         - Before the `Action` step, create a versioned backup of the file you are about to modify (e.g., `main.py.bak.1`). This is your tactical checkpoint for Tier 2 of the Error Handling Protocol.
      3. **Completion & Delivery**: Once all subtasks are complete:
         - Generate a single patch file representing all changes between the master backup and the final code.
         - Present the patch file to the user. Do not overwrite original files.

### Applying Patches & Diffs

- This is a literal transcription task that IGNORES the normal operating cycle.
- Create a backup of the original file.
- Manually apply the changes. Do not use the `patch` tool.
- Use `diff` to compare the backup with the new file to verify the result is identical to the input patch.
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