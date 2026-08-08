# Configuration files

A `.lclcfg` file gives names to LCL expressions. pylcl parses every file into an
immutable document, expands `using` declarations in source order, selects the
last definition of each name, and only then builds a runtime Module. Loading
does not evaluate ordinary definitions.

Use configuration files when expressions belong outside Python source, need
file-aware diagnostics, or should be composed from several reusable files.

## Your first `.lclcfg`

Create `settings.lclcfg`:

```lclcfg
# The version line is optional; version 1 is the default.
__LCL_VERSION__: 1

host: "api.example.test"
port: 443
base_url: f"https://{host}:{port}"
request_timeout: 15
definition_name: lhs()
release_day: parse_ymd("20240808")
release_key: to_ymd(release_day)
```

A definition is `<name>: <LCL expression>`. `=` is not a definition separator.
Blank lines and comments are ignored. A trailing comment is allowed when its
`#` is outside a string or formatted-string field.

Names introduced by configuration or by an LCL binding position cannot start
with `__`; the version metadata is the one top-level exception.

## Continue a long expression explicitly

Inside a `.lclcfg` definition, an expression continues only when the current
physical fragment ends in `\` before optional whitespace and a comment. Open
parentheses, brackets, or braces do not imply continuation.

```lclcfg
headers: { \
  "Accept": "application/json", \
  "User-Agent": "example/1.0" \
} # final fragment has no marker
```

Each non-final fragment needs its own marker. pylcl removes the markers and
comments, joins semantic fragments with one space, and still preserves original
physical source coordinates for diagnostics. Blank or comment-only lines cannot
interrupt a continuation chain.

## Split configuration with `using`

Suppose a project has this layout:

```text
config/
├── shared.lclcfg
└── production.lclcfg
```

`shared.lclcfg` contains defaults:

```lclcfg
host: "api.example.test"
request_timeout: 10
retry_count: 2
```

`production.lclcfg` expands those definitions at the `using` position:

```lclcfg
using "shared.lclcfg"

# Later definitions override earlier expanded definitions.
request_timeout: 30
base_url: f"https://{host}/v1"
retry_delay: request_timeout // retry_count
```

This is C-style expansion, not a runtime import or parent Module. The resulting
Module has `host`, `request_timeout`, `retry_count`, `base_url`, and
`retry_delay` at one level. Ordinary expression references create dependencies;
`using` itself creates none.

Expansion is recursive and ordered. Reusing the same file expands it again at
the new position, even if retrieval and parsing came from a cache. Duplicate
names are valid within one file or across files. The last chronological
definition wins, while provenance retains every occurrence.

Every root and target path must end exactly in `.lclcfg`. Relative targets are
resolved from the importing file's directory—not the process working directory.
Absolute paths are accepted. Cycles are rejected with a structured error.

## File-aware magic values

In a file-backed expression, `__file__` becomes the canonical absolute path of
the physical file containing that definition; `__dir__` becomes its parent
directory. They are eager string constants, not runtime names or dependency
edges. A definition expanded from a child file keeps the child's path.

```lclcfg
source_file: __file__
source_directory: __dir__
fixture: f"{__dir__}/fixtures/users.json"
```

In a `using` target, a leading `__dir__/` explicitly starts from the importing
directory and may be followed by `..` components:

```lclcfg
using "__dir__/../shared/base.lclcfg"
```

Other `__dir__` occurrences and all `__file__` text inside a path are ordinary
filename text. Calling `parse_config` without `source_path` is intentionally
pathless and rejects expression magic because there is no truthful value to
substitute.

## Load and evaluate from Python

`load_config` is asynchronous because source retrieval may be asynchronous. The
default resolver reads strict UTF-8 files (accepting one leading UTF-8 BOM),
normalizes paths, expands `using`, and returns an immutable `Config` without
evaluating any definition.

This complete example writes two isolated files, loads the root, inspects
precedence, creates a Frame from the resulting Module, evaluates values, and
closes the Frame:

<!-- pylcl-exec -->
```python
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from pylcl.config import evaluate_config, load_config
from pylcl.types import FrameId


async def main() -> None:
    with TemporaryDirectory(prefix="pylcl-config-guide-") as directory:
        root = Path(directory)
        shared = root / "shared.lclcfg"
        application = root / "application.lclcfg"
        shared.write_text(
            'host: "api.example.test"\n'
            "request_timeout: 10\n"
            "retry_count: 2\n",
            encoding="utf-8",
        )
        application.write_text(
            'using "shared.lclcfg"\n'
            "request_timeout: 30\n"
            'base_url: f"https://{host}/v1"\n'
            "retry_delay: request_timeout // retry_count\n",
            encoding="utf-8",
        )

        config = await load_config(application)
        assert tuple(config.definitions) == (
            "host",
            "request_timeout",
            "retry_count",
            "base_url",
            "retry_delay",
        )
        assert len(config.history["request_timeout"]) == 2
        assert await evaluate_config(config, "base_url") == "https://api.example.test/v1"

        module = config.to_module("application")
        frame = config.frame_factory().create(FrameId("request"))
        try:
            assert frame.module.definitions == module.definitions
            assert await frame.get("request_timeout") == 30
            assert await frame.get("retry_delay") == 15
        finally:
            await frame.close()


asyncio.run(main())
```

`Config.definitions` maps each name to its final `ConfigDefinition`.
`Config.history[name]` is the complete chronological provenance for that name.
`Config.expanded` retains all expanded occurrences. Conversion with
`to_module()` copies only the final expression ASTs and performs no evaluation.

`Config.frame_factory()` is convenient when several independent runs share one
loaded configuration. Every created Frame has its own cache and must be closed.
`evaluate_config(config, name)` is the small convenience for evaluating one name;
it owns and always closes its temporary Frame.

Both APIs use pylcl's canonical runtime hierarchy by default. That makes
`lhs()`, `parse_ymd`, `to_ymd`, ordinary safe builtins, and the reviewed
standard namespaces available to config definitions. Pass an explicit parent
when an application owns a different runtime base; construct a raw
`FrameFactory(config.to_module())` only when a hierarchy-free Module is
intentional.

## Parse text without reading files

Use `parse_config(text, source_name="<memory>", source_path=None)` when another
host already owns the text. It returns one unresolved `ConfigDocument`: it does
not read or expand `using` targets.

```python
from pylcl.config import parse_config

document = parse_config("answer: 6 * 7\n", source_name="generated settings")
assert document.version == 1
assert len(document.declarations) == 1
```

Supplying `source_path=Path("virtual.lclcfg")` enables `__file__` and `__dir__`
substitution but still performs no read.

## Limits and controlled resolvers

Pass `ConfigLoadLimits` to cap distinct sources, using depth, total decoded
characters, and declarations before excess work is requested or parsed.
`ConfigLoader` is reusable by concurrent tasks in one event loop and provides
single-flight retrieval, cancellation isolation, successful parse caching, and
retry after failure.

Applications can provide a custom async `ConfigSourceResolver` for controlled
storage. Resolved sources remain path-backed: they provide immutable text,
identity, display name, and canonical path so relative targets and magic values
stay deterministic. The default `FileConfigResolver` also supports an optional
allowed-root containment policy.

## Errors and trust boundary

Configuration failures derive from `LclConfigError`. Narrow subtypes distinguish
syntax, version, `using`, cycle, limit, and lifecycle failures. Diagnostics keep
the physical file span and using chain where available. Retrieval failures
retain their original exception as the cause.

Loading and parsing do not execute definitions. Evaluation is still trusted-code
configuration handling, not a hostile-file sandbox: host values and functions
can expose ordinary Python capabilities, side effects, and blocking behavior.
Review resolvers and presets, apply operational limits, and do not accept
untrusted expressions as if pylcl were security isolation.

For every edge case and API contract, continue with the
[detailed `.lclcfg` reference](../configuration.md). To understand the runtime
created from final definitions, return to [Modules and Frames](runtime.md).
