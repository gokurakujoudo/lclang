# M002: packaging skeleton

## Contract

- The distribution and import package are both named `pylcl`.
- The package requires Python 3.14 or newer and has no runtime dependencies.
- Version `0.0.0` denotes the pre-language foundation; public releases advance
  to 0.1, 0.2, 0.3, and 0.4 at their respective gates.
- The build backend is Python-only and produces a platform-independent wheel.
- The root MIT license and both README files are included in source artifacts.
- Importing `pylcl` exposes `__version__` without importing optional tooling.

## Acceptance

- Standard-library tests can read valid project metadata.
- `import pylcl` succeeds under Python 3.14 and reports `0.0.0`.
- Project metadata declares no `dependencies` array.
- Package data contains `py.typed` for typed-library discovery.
