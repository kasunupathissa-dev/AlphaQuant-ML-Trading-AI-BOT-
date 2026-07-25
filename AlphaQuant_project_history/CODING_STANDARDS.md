# AlphaQuant Coding Standards

This document defines the coding standards and best practices for the AlphaQuant project to ensure code quality, maintainability, and consistency.

## Python Version

-   The project targets **Python 3.12** and above.
-   All code must be compatible with this version.

## Formatting

-   Code should adhere to **PEP 8** style guidelines.
-   Use an automated formatter like **Black** with a line length of 100 characters.

## Naming Conventions

-   **Modules:** `lowercase_with_underscores.py` (e.g., `feature_library.py`).
-   **Classes:** `CamelCase` (e.g., `AlphaQuantV7`).
-   **Functions/Methods:** `lowercase_with_underscores()` (e.g., `calculate_features`).
-   **Variables/Constants:** `UPPERCASE_WITH_UNDERSCORES` for module-level constants (e.g., `TARGET_ASSETS`). `lowercase_with_underscores` for local variables.

## Folder Structure

-   **`src/`**: All main Python source code.
-   **`tests/`**: All unit and integration tests.
-   **`models/`**: Serialized `.pkl` model files (ignored by git).
-   **`logs/`**: CSV trade logs and application logs (ignored by git).
-   **`scripts/`**: Helper scripts for deployment, database management, etc.

## Asynchronous Standards

-   Use the `asyncio` library for all I/O-bound operations, especially network calls.
-   Use `async def` for all coroutines.
-   Never use blocking calls (like `time.sleep()` or standard `requests`) inside an `async` function. Always use `await asyncio.sleep()` and `aiohttp`.

## Logging

-   **Production:** Use the `logging` module to write structured logs to a file. Do not use `print()` for important information.
-   **Debugging:** `print()` statements are acceptable for temporary debugging but must be prefixed with `[DEBUG]` and removed before merging to `main`.

## Exception Handling

-   **Never use a bare `except:` clause.** Always specify the exception type (e.g., `except ccxt.NetworkError as e:`).
-   Log all exceptions with a clear error message indicating what operation failed and why.
-   For critical operations (like trade execution), implement a retry mechanism with exponential backoff for transient network errors.

## Type Hints

-   All new functions and methods must include PEP 484 type hints for all arguments and return values.
-   Example: `def calculate_zscore(series: pd.Series, period: int = 30) -> np.ndarray:`

## Testing Requirements

-   **Unit Tests:** All new functions in the `feature_library.py` or other utility modules must be accompanied by unit tests in the `tests/` directory.
-   **Integration Tests:** The data pipeline and live engine should have integration tests to verify component interactions.
-   **Validation:** All models must be validated using the `validation_suite_v7.py` before being considered for deployment.

## Documentation Requirements

-   All classes and public functions must have a docstring explaining their purpose, arguments, and return values.
-   The `CHANGELOG.md` and `README.md` must be updated as part of any new feature release.

## Security Requirements

-   **No Secrets in Code:** No API keys, passwords, or other credentials may be hardcoded. They must be loaded from environment variables using `os.getenv()`.
-   **Input Validation:** Sanitize all external inputs, especially any data that might be used in database queries, to prevent injection attacks.

## Performance Guidelines

-   Favor vectorized `pandas` and `numpy` operations over Python loops for data manipulation.
-   Use asynchronous I/O for all network calls to avoid blocking the event loop.
-   Profile memory and CPU usage before deploying any new feature that involves heavy computation.
