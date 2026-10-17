# Contributing

Contributions to `buienradar` are welcome. Keep changes focused, tested, and compatible with the library's existing public API.

## Before opening a change
1. Read `AGENTS.md` and `AI_POLICY.md`.
2. Review the relevant implementation, tests, package metadata, and CI configuration.
3. Search existing issues and pull requests for related work.
4. For significant behavior or API changes, describe the intended change and compatibility impact before implementation.

## Development
- Use the Python version and dependency constraints declared by the project.
- Follow existing formatting, typing, naming, and documentation conventions.
- Keep the change limited to the problem being addressed.
- Validate coordinates and other external inputs where appropriate.
- Handle HTTP failures, malformed payloads, and parsing errors explicitly.
- Avoid depending on live Buienradar services for routine tests; prefer fixtures and mocked HTTP responses.
- Do not commit credentials, access tokens, private data, generated environment files, or unrelated formatting changes.

## Tests and checks
Inspect the repository's current test and CI configuration and run the relevant checks before submitting a pull request. Add regression tests for bug fixes and tests for new behavior. Do not claim a check passed unless it was actually executed. If a check cannot be run, explain why in the pull request.

## Pull requests
Include:
- A concise summary of the problem and the proposed solution.
- Relevant issue links, if applicable.
- Any public API, output-shape, dependency, or compatibility implications.
- Tests and quality checks performed, including failures or checks not run.
- Documentation updates for user-visible changes.

Keep pull requests focused and explain why the change is needed. Do not include unrelated refactoring.

## AI-assisted contributions
AI tools may assist with investigation, implementation, and review, but contributors must verify their output. Follow `AI_POLICY.md`, review all generated changes, and ensure tests and documentation reflect actual behavior.
