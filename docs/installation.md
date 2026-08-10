# Installation

`lclang` requires Python 3.14 or newer and has no third-party runtime
dependencies.

## Install from PyPI

Create or activate a virtual environment, then install the package:

```console
python -m pip install lclang
```

Confirm the installed version and import path:

```console
python -c "import lclang; print(lclang.__version__); print(lclang.__file__)"
```

## Install from a source checkout

From the repository root:

```console
python -m pip install .
```

For editable development installation, follow the
[Local Development Guide](development/README.md).

## Runtime model

The distribution and import name are both `lclang`. The wheel is pure Python
and platform independent. Importing the package performs no filesystem,
process, or network setup.

Continue with the [Quick Start Guide](quick-start.md).
