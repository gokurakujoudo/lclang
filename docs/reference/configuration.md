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
using f"{__dir__}/parts/common.lclcfg"
using f"{__dir__}/parts/{profile}.lclcfg"
using? f"{__dir__}/parts/local.lclcfg"
using? f"{__dir__}/parts/{profile}-local.lclcfg"
```

Blank lines and full-line comments are ignored. A trailing `#` comment is valid
after version metadata, a definition, a continuation marker, or any file introduction. A
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

Start every `using`, `using?`, `import`, and `import?` target with
`f"{__dir__}/..."`. The defining file's directory is then explicit at each
introduction, including nested files. For example,
`import f"{__dir__}/services/pricing.lclcfg" as pricing` loads a sibling module,
and `using f"{__dir__}/../shared.lclcfg"` loads a file in the parent directory.

Every root and introduction target ends exactly in `.lclcfg`. Absolute targets
are used directly. Existing relative targets still resolve from the importing
file's directory; the legacy literal `__dir__/` prefix is also supported.
The optional filesystem `allowed_root` policy can reject a resulting path
after normalization.

Files decode as UTF-8; a BOM is accepted only at byte zero. Loading performs no
globbing or network access. A `using` target may be a literal string or an LCL
f-string and must evaluate to non-empty text ending in `.lclcfg`; other target
expression forms are rejected.

## Expansion and precedence

Named imports use `import f"{__dir__}/part.lclcfg" as module`, or `import?` when the
direct target may be absent. The alias may be a qualified name. An imported
file expands in its own configuration context; it cannot read preceding
definitions from the importing file. Explicit loading overrides and builtins
remain available. Its complete subtree is validated before insertion.

Imported definition names and free references to locally defined roots receive
the alias prefix. Undeclared references remain external inputs. Function
parameters and other lexical bindings keep their original names. Repeated
imports into an alias merge fields in source order; an empty existing file still
establishes the namespace. An absent optional target establishes nothing.

Qualification uses the complete expanded child subtree, so forward references
to its definitions become local too. Existing inferred scopes and explicit
empty namespaces count as local roots. Undeclared external names and function
parameters retain their meanings. Each occurrence is qualified independently;
introducing another file later cannot retroactively rewrite an external name.
Physical file origins, positions, declaration history, and sticky masks remain
attached to their original definitions. Namespaces and their ancestors cannot
also be ordinary values. A later parent declaration cannot repair an invalid
child subtree.

`NEED_OVERRIDE` and `RUNTIME_OVERRIDE` are complete-definition placeholders.
Both fail only when an unfilled value is requested. `NEED_OVERRIDE` requires a
later configuration definition or CLI override. `RUNTIME_OVERRIDE` also accepts
host inputs, including `None`; its declaration replaces an earlier configuration
value rather than preserving that value as a default.

`using` is C-style source-order expansion: the child's recursively expanded
definitions are inserted at the declaration position. Every occurrence expands,
even when retrieval and parsing use a cached immutable snapshot. Direct and
indirect cycles are errors.

`using?` has the same target syntax and expansion rules as `using`, but skips
its declaration when the directly requested file does not exist. The `?` must
immediately follow `using`. A skipped declaration contributes no definitions
or history. An existing file still reports retrieval, UTF-8 decoding, syntax,
version, nested required-file, cycle, and resource-limit errors. Dynamic target
evaluation and validation failures are never suppressed.

`ConfigUsing.optional` is a Boolean flag defaulting to `False`; parsing
`using?` sets it to `True`. The unresolved document retains the declaration
even when later loading skips a missing source. Parsed declarations still
participate in the loader's existing declaration limits.

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

Custom resolvers signal a directly requested source's absence by raising
`FileNotFoundError`. Other retrieval and authorization exceptions remain load
errors, including `KeyError`; they do not indicate optional absence. Filesystem
authorization is checked before retrieval, including for absent paths.

```python
from pathlib import Path

from lclang.config import load_config


async def read_result() -> object:
    config = await load_config(Path("settings.lclcfg"))
    async with config.to_frame() as frame:
        return await frame.get("result")
```

`Config.definitions` exposes final declarations, `Config.history` exposes
provenance, and `Config.to_frame(*, preset=None)` creates a fresh canonical
Frame for direct execution. It is exactly equivalent to
`define_frame(config.to_module(), preset=preset)`: creation is synchronous and
lazy, each call owns independent snapshots, and the optional preset is a
dictionary of host inputs or `None`. Configuration definitions take precedence
over preset inputs. Source spans, sticky masking, builtin lookup, and validation
follow the same Module/Frame rules. Use
`async with config.to_frame(preset={"environment": environment}) as frame:`
to share named results within one closed scope.

`Config.to_module()` creates an immutable Module for advanced composition, and
`Config.frame_factory()` creates reusable independent-Frame policy with presets,
parents, and evaluation limits. Callers own Frames they create and should use
them as async context managers;
`evaluate_config` owns and always closes its temporary Frame.

`Config.masked_names` exposes the immutable exact-name mask policy accumulated
from expanded declarations. The final value still follows ordinary
last-definition-wins precedence; the mask flag is sticky across those
overrides.

`ConfigImport(target, span, ordinal, alias, optional=False)` is the immutable
public import declaration. Its target shares `ConfigUsing`'s contract; the alias
is a static qualified name and `optional` must be Boolean. `ConfigDeclaration`
includes definitions, shared introductions, and independent imports.
`Config.namespace_names` is a keyword-only frozenset, empty by default.
`Config.to_module()` preserves those reservations. Empty-namespace proxy
definitions are runtime metadata and do not appear in `Config.history`.

Each expansion placement adds a detached `ConfigLoadFrame` to a copied
diagnostic. Shared source tasks retain their original exceptions, so concurrent
callers keep independent loading routes. Concrete exception classes, codes,
direct causes, and Python tracebacks survive propagation. A dynamic child target
failure shows both loading and evaluation routes. Loading uses the child's
original names; evaluation after import uses the qualified runtime names.
See [configuration composition](../tutorials/17-configuration-composition.md)
for complete examples and expected diagnostics.

Config-created Frames use the canonical lclang hierarchy by default. Definitions
therefore have the root `lhs()` function (the current definition name), builtin
`parse_ymd`/`to_ymd` date conversion, the `recursive` fixed-point helper, safe
Python builtins, and reviewed standard namespaces. An explicit parent replaces
the canonical imports layer.

`ConfigLoadLimits` caps distinct paths, recursive depth, decoded characters,
and declarations. `ConfigLoader` is safe for concurrent tasks in one event loop,
uses per-path single-flight, shields owners from waiter cancellation, retries
failed loads, and rejects cross-loop reuse.

Missing optional sources are not cached. A later occurrence or load retries
retrieval and can discover a file that has appeared; successful source
snapshots keep their ordinary cache behavior. Concurrent required and optional
requests share retrieval while each declaration applies its own missing-file
policy. Cancellation always propagates.

The language is for trusted application configuration, not hostile-code
sandboxing. Evaluation retains the ordinary powers of host-provided values and
callables.
