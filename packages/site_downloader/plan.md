# Migration Plan - yt_bulk_cc v2 (TypeScript + Playwright)

## 1. Scope & Goals

We are migrating the *feature set* of the **legacy Bash/Node repo**
(`functions/*`) into the new **TypeScript monorepo** (`packages/site_downloader/*`)
and renaming the CLI from `swissbook` → `yt_bulk_cc`.

Goals:

| Priority | Goal                                                                            |
| -------- | ------------------------------------------------------------------------------- |
| P0       | Preserve every user-facing CLI flag & behaviour that existed in the old repo.   |
| P0       | Offer a single self-contained binary (`yt_bulk_cc`) installable via `npm i -g`. |
| P1       | Keep or improve the annoyance-hiding fidelity ( 170 CSS rules).                 |
| P1       | Port the most valuable Bash test cases to Jest (unit) & Playwright (e2e).       |
| P2       | Deprecate shell wrappers once parity is verified; document migration path.      |

## 2. Gap Analysis (what's missing today)

| Area                                                                              | Status                                                                                                                                    | Detail / Action                                                                                |
| --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Project name & CLI name**                                                       | ❌ Still `swissbook` in `package.json`, `cli/index.ts`.                                                                                    | Rename to `yt_bulk_cc`; update bin, import paths, README.                                      |
| **Annoyances CSS**                                                                | ⚠️ Reduced to 3 rules.                                                                                                                    | Copy full `functions/pdf_rendering/annoyances.css` → `src/core/annoyances.css`.                |
| **CLI flags**                                                                     | ⚠️ Missing: `--heading-style`, `--code-style`, `--wrap-width`, `--max-scrolls`, separate `--quality` alias, per-URL `--retries` in batch. | Extend Commander definitions; thread through to business logic.                                |
| **Batch retries**                                                                 | ⚠️ Hard-coded 1.                                                                                                                          | Pass `--retries` down to PQueue worker calls.                                                  |
| **Content-to-Markdown options**                                                   | ⚠️ `TurndownService` currently created without options; no GFM toggle.                                                                    | Map CLI flags → turndown options.                                                              |
| **Helper functions** (`_extract_url_from_markdown`, `_sanitize_url_for_filename`) | ✅ Already re-implemented within the TS code path.                                                                                         | n/a                                                                                            |
| **Shell facade**                                                                  | ➖ Will be replaced by `yt_bulk_cc` command. Provide migration notes.                                                                      |                                                                                                |
| **Tests**                                                                         | ⚠️ Only logger test.                                                                                                                      | Port high-value unit tests (header generation, helper utils) and one smoke Playwright capture. |
| **Docs**                                                                          | ❌ README still references SwissBook.                                                                                                      | Rewrite.                                                                                       |

## 3. Task Breakdown

| #   | Task                                                                             | Files to add / edit                                           |
| --- | -------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| 1   | **Rename project** to `yt_bulk_cc`                                               | `package.json`, `README.md`, `src/cli/index.ts`, test imports |
| 2   | **Copy full CSS**                                                                | Replace `src/core/annoyances.css`                             |
| 3   | **Expose CLI flags** in Commander                                                | `src/cli/index.ts`, `src/adapters/contentExtractor.ts`        |
| 4   | **Wire turndown / html-to-text options**                                         | `contentExtractor.ts`                                         |
| 5   | **Batch retry flag**                                                             | `cli/index.ts`, batch handler loop                            |
| 6   | **Update default output directory names** if any SwissBook-specific paths remain | `cli/index.ts`                                                |
| 7   | **Unit tests**: header generator, helper utils, deep scroll                      | `tests/unit/*`                                                |
| 8   | **Playwright smoke test** (optional CI)                                          | `tests/e2e/*`                                                 |
| 9   | **README rewrite & examples**                                                    | `README.md`                                                   |
| 10  | **Version bump & publish script**                                                | `package.json`                                                |

Deliverables are split into *batches* so the diff remains reviewable.

---

## 4. Validation Checklist

- `pnpm install && pnpm run build` = zero TS errors
- `pnpm test` = all Jest tests pass
- Manual run:

  ```bash

  npx playwright install --with-deps
  yt_bulk_cc grab https://example.com -f pdf
  yt_bulk_cc batch urls.txt -f md --retries 3


Output files identical (or better) to legacy scripts.

- Compare render output against old CLI for a sample page (visual diff).

---

## 5. Timeline

| Day | Milestone                                        |
| --- | ------------------------------------------------ |
| 0-1 | Batch #1 - rename, CSS, basic flags, build green |
| 2   | Batch #2 - batch-retry logic, turndown options   |
| 3   | Unit tests ported                                |
| 4   | Smoke e2e, README, publish-dry-run               |
| 5   | Buffer / review / hand-off                       |

---

## 6. Compatibility & Deprecation

- Old shell wrappers will remain in `legacy/` for two minor releases with a warning banner:

  ```
  This wrapper is deprecated; use 'yt_bulk_cc grab ...' instead.
  ```

- Same environment variables (`PUPPETEER_SKIP_DOWNLOAD` etc.) continue to apply.
