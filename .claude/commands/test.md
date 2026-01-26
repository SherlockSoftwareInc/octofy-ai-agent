---
description: Run frontend unit tests and fix any failures
---

# Frontend Testing Workflow

This workflow runs the frontend test suite, analyzes failures, and automatically fixes issues.

## Steps

// turbo-all

1. **Run the test suite** in the frontend directory:
   ```bash
   npm test -- --run
   ```

2. **Analyze test failures** if any occur:
   - Read the error output and stack traces carefully
   - Identify the root cause (broken functionality, outdated tests, missing mocks, etc.)
   - Check if the failure is due to code changes or test issues

3. **Fix the issues** automatically:
   - If the application code is incorrect, fix the implementation
   - If the tests are outdated, update the test assertions
   - If dependencies are missing, install them
   - If mocks/setup is incomplete, add necessary configuration
   - Iterate until all tests pass

4. **Verify the fixes**:
   - Re-run tests to confirm all are passing
   - Ensure no new tests are broken
   - Check test coverage if applicable

5. **Summarize changes**:
   - List what was fixed
   - Explain why each fix was necessary
   - Note any new tests added or updated

## Notes

- The test suite uses **Vitest** as the test runner
- Tests use **React Testing Library** for component testing
- Mock timers with `vi.useFakeTimers()` when testing time-based behavior
- Use `--run` flag for CI/single-run mode, omit it for watch mode