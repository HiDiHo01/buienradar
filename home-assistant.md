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

## Advanced Home Assistant logging
- Add structured, actionable logging to the consuming Home Assistant integration at important boundaries: setup and unload, coordinator refreshes, upstream requests, response decoding/parsing, and recovery from expected failures.
- Use the module-level logger (for example, `_LOGGER = logging.getLogger(__name__)`) and select levels deliberately: `DEBUG` for diagnostic details, `INFO` for meaningful lifecycle events, `WARNING` for recoverable unexpected conditions, and `ERROR` for failures that prevent an operation from completing. Avoid logging every successful poll at `INFO`.
- Use lazy `%s`-style formatting. Include relevant non-sensitive context such as the operation, endpoint category, retry/timeout state, or affected data field; do not log credentials, tokens, authorization headers, personal data, or complete raw service responses.
- Log expected exceptions at the layer that can add useful context and handle them. Use `exc_info=True` (or `_LOGGER.exception(...)` inside an exception handler) when a traceback materially helps diagnosis; avoid duplicate tracebacks when the same failure is re-raised by higher layers.
- Keep debug logging useful but bounded: summarize payload shape, record counts, missing fields, parsing decisions, and timing rather than dumping large payloads or logging once per data point. Never let logging change control flow or conceal a failure.
- Verify diagnostics with Home Assistant's logger configuration, for example:

  ```yaml
  logger:
    default: warning
    logs:
      custom_components.<domain>: debug
  ```

  Replace `<domain>` with the consuming integration's actual domain. Test logging with representative success and failure cases, and ensure debug logs contain no secrets or sensitive data.
- Keep Home Assistant-specific logging configuration and imports in the consuming integration; this standalone library must remain independent of Home Assistant Core.

## Change review
For changes that may affect Home Assistant consumers, review public function signatures, returned keys and value types, timezone behavior, request timing, exception behavior, and dependency changes. Document compatibility impacts and include regression tests.
