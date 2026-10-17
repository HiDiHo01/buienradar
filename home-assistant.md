# Home Assistant Integration Guidance

This repository is a standalone Python library for retrieving and parsing Buienradar weather data. It is **not itself a Home Assistant custom integration**. These notes apply when this library is used by a Home Assistant integration or when changes are intended to improve compatibility with such consumers.

## Compatibility
- Check the consuming integration's supported Home Assistant and Python versions before changing dependencies or runtime requirements.
- Preserve the library's existing public API and return-data structure unless a breaking change is intentional, documented, and coordinated with consumers.
- Do not add Home Assistant Core imports or runtime dependencies to this standalone library without an explicit architectural decision.
- Verify dependency constraints against the consuming integration and its test environment; do not assume the latest Home Assistant release is the only supported target.

## Network and parsing behavior
- Make network failures, non-success HTTP responses, malformed JSON/XML, and invalid payloads distinguishable and actionable.
- Use bounded request timeouts and avoid exposing secrets or sensitive request details in logs.
- Keep parsing deterministic and tolerant only where the upstream format is genuinely optional or variable; do not silently fabricate weather values.
- Prefer mocked HTTP responses and representative fixtures for automated tests. Live upstream endpoints should not be required for ordinary unit tests.

## Guidance for consuming Home Assistant integrations
- Perform blocking library calls away from Home Assistant's event loop, or use an asynchronous client if the integration architecture supports one.
- Follow current Home Assistant config-entry, coordinator, entity availability, lifecycle, and shared-session guidance in the consuming integration.
- Ensure failed refreshes do not incorrectly present stale data as current or leave entities falsely available.
- Test setup/unload, refresh failures, missing fields, and public-data compatibility in the integration that consumes this package.
- Verify current Home Assistant APIs against official developer documentation and the consuming repository's declared target version.

## Change review
For changes that may affect Home Assistant consumers, review public function signatures, returned keys and value types, timezone behavior, request timing, exception behavior, and dependency changes. Document compatibility impacts and include regression tests.
