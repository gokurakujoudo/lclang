# Configuration composition

File introduction decides which names share a configuration context and where
overrides take effect. Choose that boundary before splitting a large file. A
shared deployment layer and a reusable service module usually need different
boundaries.

## Choose the introduction that matches the file

| Declaration | Context while loading the child | Runtime names | Direct missing target |
| --- | --- | --- | --- |
| `using f"{__dir__}/file.lclcfg"` | Shares preceding expanded definitions | Unchanged | Error |
| `using? f"{__dir__}/file.lclcfg"` | Shares preceding expanded definitions | Unchanged | Skip |
| `import f"{__dir__}/file.lclcfg" as m` | Independent, with explicit loading overrides and builtins | Local definitions become `m.*` | Error |
| `import? f"{__dir__}/file.lclcfg" as m` | Independent, with explicit loading overrides and builtins | Local definitions become `m.*` | Skip |

Every form accepts a quoted path or an f-string path ending in `.lclcfg`.
Relative paths start beside the introducing file. Optionality applies only to
the directly requested target. Existing files still report read, decoding,
syntax, nested dependency, cycle, and resource-limit errors.

## Share deployment settings with `using`

Use `using` when files intentionally participate in one chronological context.
That is useful for base policy, deployment overrides, and optional local settings.

<!-- lclang-doc-case: shared-context -->

`main.lclcfg`:

<!-- lclang-doc-file: main.lclcfg -->
```lclcfg
profile: "production"
using f"{__dir__}/selection.lclcfg"
rate: 0.20
total: 100 * rate
```

`selection.lclcfg`:

<!-- lclang-doc-file: selection.lclcfg -->
```lclcfg
using f"{__dir__}/{profile}.lclcfg"
```

`production.lclcfg`:

<!-- lclang-doc-file: production.lclcfg -->
```lclcfg
rate: 0.18
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config


async def main() -> None:
    config = await load_config("main.lclcfg")
    assert len(config.history["rate"]) == 2
    async with config.to_frame() as frame:
        print(await frame.get("total"))


asyncio.run(main())
```

The child reads the preceding production profile while loading. The root's
later rate wins at runtime, so the program prints `20.0`:

<!-- lclang-doc-output: stdout -->
```text
20.0
```
<!-- /lclang-doc-case -->

## Give reusable files their own names with `import`

An import first expands and validates its complete child subtree. It then
prefixes definition names and free references to names defined in that subtree.
This keeps a reusable file's own `rate` separate from the application's `rate`.

<!-- lclang-doc-case: isolated-names -->

`pricing.lclcfg`:

<!-- lclang-doc-file: pricing.lclcfg -->
```lclcfg
rate: 0.18
total: quantity * rate
```

`main.lclcfg`:

<!-- lclang-doc-file: main.lclcfg -->
```lclcfg
rate: 999
import f"{__dir__}/pricing.lclcfg" as retail
import f"{__dir__}/pricing.lclcfg" as wholesale
wholesale.rate: 0.12
result: retail.total + wholesale.total
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config


async def main() -> None:
    config = await load_config("main.lclcfg")
    async with config.to_frame(preset={"quantity": 100}) as frame:
        print(await frame.get("retail.total"))
        print(await frame.get("wholesale.total"))
        print(await frame.get("result"))


asyncio.run(main())
```

Each total uses its own qualified rate. `quantity` is undeclared in the child,
so it remains an external input shared by the two instances. The root rate
does not replace either imported rate. The program prints:

<!-- lclang-doc-output: stdout -->
```text
18.0
12.0
30.0
```
<!-- /lclang-doc-case -->

External references can also resolve to final root configuration definitions.
Import isolation governs the child's loading context and local names; it does
not seal off undeclared runtime inputs. Declare defaults or placeholders for
inputs that should belong to the module instead of relying on accidental root
names.

## Preserve lexical variables

Import qualification follows free references. Function parameters,
comprehension targets, handler bindings, and context-manager bindings stay local.

<!-- lclang-doc-case: lexical-names -->

<!-- lclang-doc-file: functions.lclcfg -->
```lclcfg
offset: 2
add: m -> offset + m
result: add(3)
```

<!-- lclang-doc-file: main.lclcfg -->
```lclcfg
import f"{__dir__}/functions.lclcfg" as m
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config


async def main() -> None:
    config = await load_config("main.lclcfg")
    async with config.to_frame() as frame:
        print(await frame.get("m.result"))


asyncio.run(main())
```

The function's free `offset` becomes `m.offset`. Its parameter named `m`
remains the argument `3`, so the result is `5`:

<!-- lclang-doc-output: stdout -->
```text
5
```
<!-- /lclang-doc-case -->

## Nest aliases and merge fields deliberately

Aliases may be qualified, such as `services.pricing`. Nested aliases concatenate.
Repeated imports into the same alias replace only matching fields. References
are qualified for each occurrence; a later file does not retroactively make an
earlier undeclared input local.

<!-- lclang-doc-case: nested-fields -->

<!-- lclang-doc-file: main.lclcfg -->
```lclcfg
import f"{__dir__}/service.lclcfg" as services.api
import f"{__dir__}/patch.lclcfg" as services.api
```

<!-- lclang-doc-file: service.lclcfg -->
```lclcfg
host: "api.example.com"
port: 443
import f"{__dir__}/retry.lclcfg" as retry
endpoint: f"{host}:{port}"
```

<!-- lclang-doc-file: retry.lclcfg -->
```lclcfg
attempts: 3
```

<!-- lclang-doc-file: patch.lclcfg -->
```lclcfg
port: 8443
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config


async def main() -> None:
    config = await load_config("main.lclcfg")
    assert len(config.history["services.api.port"]) == 2
    async with config.to_frame() as frame:
        print(await frame.get("services.api.endpoint"))
        print(await frame.get("services.api.retry.attempts"))


asyncio.run(main())
```

The patch replaces the port and retains the host, endpoint, and retry settings.
The endpoint sees the final port winner, and the program prints:

<!-- lclang-doc-output: stdout -->
```text
api.example.com:8443
3
```
<!-- /lclang-doc-case -->

For an intentional deployment override, `services.api.port: 8443` in the root
is often easier to follow than importing a one-field patch under the same alias.
Keep the source order visible; several files silently overriding the same key
make provenance harder to read.

## Distinguish an empty module from an absent optional module

An existing empty imported file creates a namespace. A missing optional file
creates nothing, including no definitions or history.

<!-- lclang-doc-case: empty-and-absent -->

`empty.lclcfg` is deliberately empty:

<!-- lclang-doc-file: empty.lclcfg -->
```lclcfg
```

<!-- lclang-doc-file: main.lclcfg -->
```lclcfg
import f"{__dir__}/empty.lclcfg" as empty
import? f"{__dir__}/missing.lclcfg" as absent
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang import FrameProxy
from lclang.config import load_config


async def main() -> None:
    config = await load_config("main.lclcfg")
    assert not config.history
    async with config.to_frame() as frame:
        empty = await frame.get("empty")
        assert isinstance(empty, FrameProxy)
        print(await empty.field_names())
        print(frame.has("absent"))


asyncio.run(main())
```

The empty namespace has no fields, while the absent namespace cannot be found:

<!-- lclang-doc-output: stdout -->
```text
[]
False
```
<!-- /lclang-doc-case -->

Ordinary values at a namespace or one of its ancestors conflict with that
namespace, including values supplied by a preset. Qualified field overrides
remain valid. For example, importing as `service` and then declaring `service: 42`
fails; declaring `service.port: 8443` is valid. Do not use a whole-object override
to replace an imported namespace.

## Require an explicit winning definition

Use `NEED_OVERRIDE` for a module value that the configuration author must supply.
A later configuration declaration or CLI override replaces the placeholder.
Lower-priority host or preset values do not satisfy it. The placeholder fails
only if evaluation reaches that definition.

<!-- lclang-doc-case: required-value -->

<!-- lclang-doc-file: service.lclcfg -->
```lclcfg
port: NEED_OVERRIDE # Deployment must select the listener.
result: port + 1
```

<!-- lclang-doc-file: main.lclcfg -->
```lclcfg
import f"{__dir__}/service.lclcfg" as service
service.port: 8443
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config


async def main() -> None:
    config = await load_config("main.lclcfg")
    async with config.to_frame() as frame:
        print(await frame.get("service.result"))


asyncio.run(main())
```

The later qualified definition satisfies the requirement. The program prints:

<!-- lclang-doc-output: stdout -->
```text
8444
```
<!-- /lclang-doc-case -->

This skipped reference does not raise, because the false branch never requests
`required`:

```lclcfg
required: NEED_OVERRIDE
result: required if False else 100
```

With `True`, requesting `result` fails with `required needs a value`. A caller's
`Frame.get("required", fallback)` does not hide the failure: the name exists.
Defaults and placeholders both establish local names for import qualification.
Use a comment to state the unit and where the override should come from.

## Reserve a value for runtime injection

`RUNTIME_OVERRIDE` permits code or preset values to satisfy the name. It is useful
when configuration must own a qualified name but Python owns the actual value.
An explicit `None` is a supplied value. Prefer an ordinary default or
`NEED_OVERRIDE` unless runtime injection is the intended contract.

<!-- lclang-doc-case: runtime-input -->

<!-- lclang-doc-file: service.lclcfg -->
```lclcfg
port: RUNTIME_OVERRIDE # Python supplies the listener.
result: port + 1
```

<!-- lclang-doc-file: main.lclcfg -->
```lclcfg
import f"{__dir__}/service.lclcfg" as service
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config


async def main() -> None:
    config = await load_config("main.lclcfg")
    async with config.to_frame(preset={"service.port": 9000}) as frame:
        print(await frame.get("service.result"))


asyncio.run(main())
```

The supplied qualified value is visible to the dependant expression. The program
prints:

<!-- lclang-doc-output: stdout -->
```text
9001
```
<!-- /lclang-doc-case -->

The following order discards the earlier `8080`; it does not make that value a
fallback for an unfilled runtime reservation:

```lclcfg
service.port: 8080
import f"{__dir__}/service.lclcfg" as service
```

Both override markers are complete right-hand sides. Expressions such as
`RUNTIME_OVERRIDE ?? 8080` and `[NEED_OVERRIDE]` are syntax errors.

## Keep loading inputs separate from runtime requirements

The import's outer target uses the importing file's preceding definitions.
Once selected, its child starts an independent loading context. A dynamic
introduction inside that child cannot borrow the parent's configuration values.
Explicit loader overrides use the child's original, unqualified names.

An unfilled placeholder used to choose another file fails during loading,
before the alias has been applied:

<!-- lclang-doc-case: loading-failure -->

<!-- lclang-doc-file: main.lclcfg -->
```lclcfg
import f"{__dir__}/service.lclcfg" as m
```

<!-- lclang-doc-file: service.lclcfg -->
```lclcfg
profile: NEED_OVERRIDE
using f"{__dir__}/profiles/{profile}.lclcfg"
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import LclConfigUsingError, load_config


async def main() -> None:
    try:
        await load_config("main.lclcfg")
    except LclConfigUsingError as error:
        print(error)


asyncio.run(main())
```

The output records both introduction declarations and the original `profile`
requirement. There is no `m.profile` yet:

<!-- lclang-doc-output: stdout -->
```text
Error in loading config file "main.lclcfg" [LCL4201]:
  at "main.lclcfg":1:1
    import f"{__dir__}/service.lclcfg" as m
  at "service.lclcfg":2:1
    using f"{__dir__}/profiles/{profile}.lclcfg"
  Error in evaluating profile [LCL3001]:
    profile at "service.lclcfg":1:10
      profile: NEED_OVERRIDE
               ^^^^^^^^^^^^^
  Cause: profile needs a value
```
<!-- /lclang-doc-case -->

Passing `overrides={"profile": "production"}` can select the child file, but it
does not replace the final `m.profile` definition. This two-stage contract is
easy to misuse. Prefer selecting the variant at the outer boundary:

```lclcfg
profile: "production"
import f"{__dir__}/profiles/{profile}.lclcfg" as service
```

## Read the runtime failure without losing its context

A runtime failure uses actual qualified names and retains values read before
the failure. Rendering the error never evaluates an unused definition.

<!-- lclang-doc-case: evaluation-failure -->

<!-- lclang-doc-file: main.lclcfg -->
```lclcfg
import f"{__dir__}/metrics.lclcfg" as m
result: m.ratio * 100
```

<!-- lclang-doc-file: metrics.lclcfg -->
```lclcfg
total: 5
count: 0
ratio: total / count
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config
from lclang.errors import LclEvaluationError


async def main() -> None:
    config = await load_config("main.lclcfg")
    async with config.to_frame() as frame:
        try:
            await frame.get("result")
        except LclEvaluationError as error:
            assert isinstance(error.__cause__, ZeroDivisionError)
            print(error)


asyncio.run(main())
```

The root requests `m.ratio`; division reads `5` and `0` before failing. The
output includes the physical child source and those qualified read values:

<!-- lclang-doc-output: stdout -->
```text
Error in evaluating result [LCL3001]:
  result at "main.lclcfg":2:9
    result: m.ratio * 100
  m.ratio at "metrics.lclcfg":3:8
    ratio: total / count
           ^^^^^^^^^^^^^
    m.total = (int) 5
    m.count = (int) 0
Cause: ZeroDivisionError: division by zero
```
<!-- /lclang-doc-case -->

Cached failures keep their first snapshot. Explicit recalculation creates a new
snapshot without invalidating cached dependants. Mark sensitive exact names with
`!`; derived sensitive values need their own marker because masking is not
transitive. See [errors and inspection](07-errors-and-inspection.md).

## Compose Python Modules before creating Frames

`Frame.mixin()` updates host values. Ordinary definitions in that Frame retain
priority over same-name values. Use `Module.mixin()` when the intended change is
a replacement definition. It returns a new Module and leaves both input Modules
and existing Frames unchanged.

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang import define_frame, define_module


async def main() -> None:
    base = define_module("base", {"port": "443", "result": "port + 1"})
    patch = define_module("deployment", {"port": "8443"})
    combined = base.mixin(patch)
    async with define_frame(base) as original, define_frame(combined) as configured:
        assert await original.get("result") == 444
        assert await configured.get("result") == 8444


asyncio.run(main())
```

The original result is `444`, and the composed result is `8444`. Composition
combines definitions before any evaluation, so the dependant uses the new port.
Masks remain sticky, namespaces are combined, and invalid combined structures
are rejected. `RUNTIME_OVERRIDE` is the explicit exception that permits a host
value to satisfy a definition reservation.

CLI configuration and overrides are also assembled before evaluation. For
example, `--override service.port "LCL[9000]"` supplies integer `9000` to
dependants. An unmarked `9000` argument remains text. See
[command-line applications](09-command-line-applications.md).

## Keep composition predictable

- Start every introduction target with `f"{__dir__}/..."`. Each file then
  states its own path base explicitly. Use `f"{__dir__}/../shared.lclcfg"` for
  a parent directory and the same convention inside reusable child files.
- Use `using` for files whose shared namespace and chronological overrides are
  intentional. Use `import` for reusable modules with their own defaults.
- Give required local inputs a default or placeholder. An undeclared input
  deliberately remains external, which can couple a module to root names.
- Put deployment overrides close to their introductions. Check `Config.history`
  when a final value is surprising.
- Keep variant selection at the outer import where practical. Avoid using
  unfilled runtime reservations to choose files during loading.
- Treat optionality as an absence policy. Do not use it to conceal an invalid
  existing file or a missing required dependency.
- Validate reusable children on their own. A parent cannot repair `a: 1` together
  with `a.b: 2` by adding a later `m.a: FRAME_PROXY`.
- Reuse loaders for immutable successful source snapshots, and create fresh
  Frames for independent runs. Neither loading nor recalculation automatically
  invalidates dependant snapshots.

## Combine a reusable service with deployment policy

This final example keeps profile selection in the deployment file, service
relationships in the reusable child, and a secret in runtime inputs. An optional
local file changes one field after import.

<!-- lclang-doc-case: deployment-combination -->

<!-- lclang-doc-file: main.lclcfg -->
```lclcfg
using f"{__dir__}/deployment.lclcfg"
import f"{__dir__}/profiles/{profile}.lclcfg" as service
using? f"{__dir__}/local.lclcfg"
result: {endpoint=service.endpoint, retries=service.retries, authenticated=service.authenticated}
```

<!-- lclang-doc-file: deployment.lclcfg -->
```lclcfg
profile: "production"
```

<!-- lclang-doc-file: profiles/production.lclcfg -->
```lclcfg
using f"{__dir__}/../service-defaults.lclcfg"
host: "api.example.com"
```

<!-- lclang-doc-file: service-defaults.lclcfg -->
```lclcfg
port: 443
retries: 2
token!: RUNTIME_OVERRIDE
endpoint: f"https://{host}:{port}"
authenticated: bool(token)
```

<!-- lclang-doc-file: local.lclcfg -->
```lclcfg
service.retries: 5
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config


async def main() -> None:
    config = await load_config("main.lclcfg")
    async with config.to_frame(preset={"service.token": "injected credential"}) as frame:
        result = await frame.get("result")
        print(result)
        assert frame.is_masked("service.token")


asyncio.run(main())
```

The deployment selects `production` before import. The child's `using` shares
its service context, so `host`, `port`, and the derived endpoint receive the same
alias. The local file replaces `service.retries` with `5`. The runtime token
satisfies the reservation and remains masked; only its Boolean presence is
included in the result:

<!-- lclang-doc-output: stdout -->
```text
LclRecord(endpoint='https://api.example.com:443', retries=5, authenticated=True)
```
<!-- /lclang-doc-case -->

Removing `local.lclcfg` would keep retries at `2`. Removing the runtime token
would fail only when `authenticated` is requested. A deployment can also provide
a later configuration or CLI definition for a reserved field; precedence is
decided before the derived endpoint or authentication expression runs.

Configuration remains trusted code with the ordinary capabilities of supplied
Python objects. Import isolation controls name composition; it provides no
hostile-code sandbox.

[Previous: Python utilities for downstream applications](16-python-utilities.md) | [Return to the series introduction](README.md)
