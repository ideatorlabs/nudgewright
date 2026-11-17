# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-17

### Added

- Initial release.
- Input models: `Business`, `Offer`, `Festival`, `Event`, `Weather`, `Loyalty`, `Customer`, `Context`.
- Signal catalogue with `auto | always | never` switches per business.
- Composer pipeline: gather, pick (at most three slots: why now > why this person > what to offer),
  write, check, explain.
- Fixed guardrails: owner offer only, no private customer detail, sensitive sectors, one line,
  maximum length, safe-line fallback.
- `Composed` result with `used`, `skipped`, `guardrails`, `level`, `why()` and `summary()`.
- Replaceable English phrasebook with whitelisted template fields.
- Optional Open-Meteo weather client with an injectable fetcher and a TTL LRU cache.
- JSON loaders and the `nudgewright` command line (`compose`, `signals`).

[Unreleased]: https://github.com/ideatorlabs/nudgewright/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ideatorlabs/nudgewright/releases/tag/v0.1.0
