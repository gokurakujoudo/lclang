# `.lclcfg` configuration files

The implemented configuration API lives under `lclang.config`. It parses trusted
UTF-8 configuration files into the existing custom LCL AST, expands other files
without evaluating definitions, and converts final winners into reusable runtime
Modules and Frames. It never uses Python `eval`, `exec`, or Python-AST compilation.

## File grammar

The optional first meaningful declaration selects the configuration version;
version 1 is the default.

```lclcfg
__LCL_VERSION__: 1

# Definitions use a colon.
base: 2
total: (base + \ # the next physical line continues
  3)

# The target is one quoted path string.
using "parts/common.lclcfg"
```

Blank lines and full-line comments are ignored. A trailing `#` comment is valid
after version metadata, a definition, a continuation marker, or `using`. A
backslash outside literals is the only continuation mechanism; open `()`, `[]`,
or `{}` never continues a definition by itself. Blank and comment-only lines are
not valid inside a continuation chain.

Definition names may be one LCL identifier or a dot-separated qualified path
of LCL identifiers. Top-level names beginning with `__` remain reserved; the
metadata name is the sole exception. `A: FRAME_PROXY` optionally declares a
scoped prefix, while `A.x: expression` infers `A` automatically.

## File magic and paths

Within a file-backed definition, `__file__` and `__dir__` become eager string
constants for the canonical absolute defining file and its parent directory.
They are not runtime variables or dependency edges. A definition expanded from
a child file retains that child's values. Pathless `parse_config` calls reject
these magic values.

Every root and `using` target ends exactly in `.lclcfg`. Absolute targets are
used directly; relative targets resolve from the importing file's directory.
A quoted target beginning with `__dir__/` explicitly starts there and may use
any number of `..` components. The optional filesystem `allowed_root` policy can
reject the resulting path after normalization.

Files decode as UTF-8; a BOM is accepted only at byte zero. Loading performs no
globbing, environment expansion, network access, or expression evaluation.

## Expansion and precedence

`using` is C-style source-order expansion: the child's recursively expanded
definitions are inserted at the declaration position. Every occurrence expands,
even when retrieval and parsing use a cached immutable snapshot. Direct and
indirect cycles are errors.

Duplicate names are valid in one or many files. The last chronological
definition wins without moving the name's first-appearance iteration position.
`Config.history` retains every occurrence. The runtime Module is created after
complete expansion and contains final winners, so forward references and later
overrides are independent of declaration order.

Scoped conflicts are checked against final winners. Exact-name replacement and
sibling leaves are valid, but two real winners such as `A` and `A.x`, or `A.x`
and `A.x.y`, are rejected before runtime conversion.

## Python API and lifecycle

`parse_config(text, source_name="<memory>", source_path=None)` synchronously
parses one unresolved document and performs no I/O. Supplying `source_path`
enables file magic without reading that path.

`await load_config(path, resolver=None, limits=None)` uses `FileConfigResolver`
by default. Embedders may provide an async `ConfigSourceResolver`; returned
sources remain path-backed so relative targets and magic stay deterministic.

```python
from pathlib import Path

from lclang.config import evaluate_config, load_config


async def read_result() -> object:
    config = await load_config(Path("settings.lclcfg"))
    return await evaluate_config(config, "result")
```

`Config.definitions` exposes final declarations, `Config.history` exposes
provenance, `Config.to_module()` creates an immutable Module, and
`Config.frame_factory()` creates reusable independent-Frame policy. Callers own
Frames they create and should use them as async context managers;
`evaluate_config` owns and always closes its temporary Frame.

Config-created Frames use the canonical lclang hierarchy by default. Definitions
therefore have the root `lhs()` function (the current definition name), builtin
`parse_ymd`/`to_ymd` date conversion, the `recursive` fixed-point helper, safe
Python builtins, and reviewed standard namespaces. An explicit parent replaces
the canonical imports layer.

`ConfigLoadLimits` caps distinct paths, recursive depth, decoded characters,
and declarations. `ConfigLoader` is safe for concurrent tasks in one event loop,
uses per-path single-flight, shields owners from waiter cancellation, retries
failed loads, and rejects cross-loop reuse.

The language is for trusted application configuration, not hostile-code
sandboxing. Evaluation retains the ordinary powers of host-provided values and
callables.
