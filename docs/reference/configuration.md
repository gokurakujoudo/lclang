# `.lclcfg` configuration files

The implemented configuration API lives under `lclang.config`. It parses trusted
UTF-8 configuration files into the existing custom LCL AST, expands other files in source order, and converts final winners into reusable runtime
Modules and Frames. It never uses Python `eval`, `exec`, or Python-AST compilation.

## File grammar

The optional first meaningful declaration selects the configuration version;
version 1 is the default.

<!-- lclang-config-parse -->
```lclcfg
__LCL_VERSION__: 1

# Definitions use a colon.
base: 2
api_token!: "secret"
total: (base + \ # the next physical line continues
  3)

# The target is a quoted path or semantic f-string.
using "parts/common.lclcfg"
using f"parts/{profile}.lclcfg"
```

Blank lines and full-line comments are ignored. A trailing `#` comment is valid
after version metadata, a definition, a continuation marker, or `using`. A
backslash outside literals is the only continuation mechanism; open `()`, `[]`,
or `{}` never continues a definition by itself. Blank and comment-only lines are
not valid inside a continuation chain.

Definition names may be one LCL identifier or a dot-separated qualified path
of LCL identifiers. Top-level names beginning with `__` remain reserved; the
metadata name is the sole exception. `A: FRAME_PROXY` remains valid optional
metadata for a scoped prefix, while `A.x: expression` infers `A` automatically.
It is not recommended for ordinary configuration layout; prefer inference and
omit the placeholder.

A single trailing `!` marks the exact definition name as masked and is not part
of that name. For example, `service.password!: expression` is referenced as
`service.password`. Once a name is marked by any expanded declaration, later
same-name definitions and runtime overrides remain masked. Masking does not
propagate to derived definitions; mark those separately when their own values
must be hidden. Verbose parse and evaluation diagnostics render a masked
expression, value, result, or failure as `*masked*`.

## Recommended layout

Keep definitions from the same scope on consecutive rows without blank lines.
Separate different scopes or functional groups with one blank line. Use an
inline `#` comment to explain an individual definition and a standalone comment
line to name each section. A `# scope: <description>` line communicates the
purpose of qualified leaves without creating a `FRAME_PROXY` declaration.

<!-- lclang-config-parse -->
```lclcfg
# scope: service endpoint
service.host: "api.example.com" # DNS name selected by deployment policy
service.port: 8443 # TLS listener

# Pricing
pricing.rate: 0.18 # Contract rate per unit
pricing.tax: 0.08 # Tax rate as a decimal
```

These rules are readability recommendations, not grammar restrictions. Blank
lines, comments, and explicit `FRAME_PROXY` declarations retain their existing
meaning.

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
globbing or network access. A `using` target may be a literal string or an LCL
f-string and must evaluate to non-empty text ending in `.lclcfg`; other target
expression forms are rejected.

## Expansion and precedence

`using` is C-style source-order expansion: the child's recursively expanded
definitions are inserted at the declaration position. Every occurrence expands,
even when retrieval and parsing use a cached immutable snapshot. Direct and
indirect cycles are errors.

A dynamic `using` f-string sees only expanded definitions occurring before its
declaration, call-supplied loader overrides at higher precedence, and canonical
builtins such as live `env`. Unresolved forward names, evaluation failures,
non-string results, empty targets, and invalid suffixes become source-spanned
`LclConfigUsingError` failures. Selecting a dynamic target evaluates the preceding definitions needed by its
f-string. Each target uses a fresh temporary Frame that is
always closed and discarded; target evaluation never seeds final runtime
caches. Complete expansion still computes final winners independently, so a
later declaration may change the eventual runtime value without retroactively
changing a target already selected.

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

`await load_config(path, resolver=None, limits=None, overrides=None)` uses
`FileConfigResolver` by default. Embedders may provide an async
`ConfigSourceResolver`; returned sources remain path-backed so relative targets
and magic stay deterministic. `ConfigLoader.load` accepts the same `overrides`
mapping. LCL AST values are lazy definitions during dynamic target evaluation;
all other values are literals.

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

`Config.masked_names` exposes the immutable exact-name mask policy accumulated
from expanded declarations. The final value still follows ordinary
last-definition-wins precedence; the mask flag is sticky across those
overrides.

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
