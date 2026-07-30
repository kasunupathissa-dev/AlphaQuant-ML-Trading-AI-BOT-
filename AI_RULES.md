# AI Assistant Coding Rules

This document outlines the rules and directives for any AI assistant working on the AlphaQuant codebase. Adherence to these rules is mandatory to ensure project stability and safety.

## Core Directives

1.  **Zero-Trust Workflow:** Always assume your internal state is stale. Before writing to any file, you **must** first use `read_file` to get the current version from the user's machine.

2.  **Atomic, Incremental Changes:** Never rewrite large blocks of code or entire files at once. Apply small, targeted, and verifiable changes.

3.  **Audit Before Writing:** Before issuing a `write_file` command, you must perform a self-audit. State the exact line numbers being changed and show the "before" and "after" code snippets as proof.

4.  **Explain Your Plan:** Before making any changes, clearly state your diagnosis of the problem and your step-by-step plan to fix it.

## Safety and Quality Directives

5.  **Preserve Backward Compatibility:** Do not make changes that break existing functionality unless explicitly tasked to do so as part of a major version upgrade.

6.  **Never Remove Functionality:** Do not remove features or code paths, even if they seem unused. Deprecate them with a comment first and ask for confirmation.

7.  **Check for Regressions:** After applying a fix, mentally (or explicitly) review the `CHANGELOG.md` to ensure you have not accidentally reintroduced a previously solved bug.

8.  **Analyze Cross-File Impact (Rule #3):** When fixing a bug in one file, you must check other files for the same pattern. State the result of this check using the format: `This bug could also exist in: [list files]`.

9.  **No Silent Failures (Rule #5):** Never use a bare `except:` to swallow an error. Always log the exception and the context of what failed.

10. **Production-Ready Code:** All code you write must adhere to the `CODING_STANDARDS.md`, including type hints, docstrings, and security protocols.

## Technical Verification Directives

11. **Check Edge Cases:** Explicitly consider edge cases for any new logic (e.g., empty DataFrames, division by zero, API returning `None`).

12. **Check Async Safety:** Ensure that no blocking I/O calls (`time.sleep`, `requests.get`) are used within `async def` functions.

13. **Check Exception Handling:** Verify that all network calls and file I/O operations are wrapped in appropriate `try...except` blocks.

## Pandas 3.0 Compatibility Directives

14. **No Uppercase Resample Aliases:** Never use uppercase frequency aliases (e.g., `resample('1H')`, `resample('T')`, `resample('S')`) which are deprecated/removed in Pandas 3.0. Always use lowercase counterparts: `resample('1h')`, `resample('1min')`, `resample('1s')`.

15. **No Chained Inplace Assignments:** Never use chained inplace assignments (e.g., `df['col'].fillna(..., inplace=True)`). Perform assignments directly (e.g., `df['col'] = df['col'].fillna(...)`) to prevent runtime errors in Pandas 3.0.
