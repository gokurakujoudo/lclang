# Configuration files

A `.lclcfg` file holds trusted LCL definitions outside Python. Loading preserves
the defining file and source positions, then creates the same Module and Frame
values used by Python applications. Ordinary results stay lazy; loading evaluates
only the definitions needed to choose dynamic file targets.

Start file introduction targets with `f"{__dir__}/..."`, including in child
files. For example, `using f"{__dir__}/shared.lclcfg"` names a sibling, and
`import f"{__dir__}/../pricing.lclcfg" as pricing` names a file in the parent
directory. This convention makes each defining file's path base explicit.

## Parse text that another system owns

Version 1 is the default. An optional version declaration must be the first
meaningful declaration. Definitions use a colon, and a backslash is the only
physical-line continuation marker. Opening a bracket alone does not continue
the declaration.

<!-- lclang-doc-case: parse-text -->

`pricing.lclcfg`:

<!-- lclang-doc-file: pricing.lclcfg -->
```lclcfg
__LCL_VERSION__: 1
# Expressions may refer to inputs supplied later.
subtotal: unit_price * quantity
total: subtotal + \
  shipping
```

Read the text and parse it without asking the parser to access a file:

<!-- lclang-doc-exec -->
```python
from pathlib import Path

from lclang.config import parse_config

text = Path("pricing.lclcfg").read_text(encoding="utf-8")
document = parse_config(text, source_name="generated pricing")
assert str(document.origin.name) == "generated pricing"
print(document.version, len(document.declarations))
```

This prints version `1` and two definitions. Metadata and comments do not
contribute definitions, and continuation keeps `total` as one expression.

<!-- lclang-doc-output: stdout -->
```text
1 2
```
<!-- /lclang-doc-case -->

## Keep related definitions together

Put definitions from one scope on consecutive rows. Separate scopes or functional
groups with a blank line. Use an inline comment to explain an individual value
and a standalone comment to name a group. Qualified leaves infer their prefixes.

```lclcfg
# scope: service endpoint
service.host: "api.example.com" # Deployment DNS name
service.port: 8443 # TLS listener

# Retry policy
retry.count: 3 # Maximum attempts
retry.delay: 0.5 # Seconds between attempts
```

`FRAME_PROXY` can declare a prefix explicitly, but ordinary files can rely on
inference. See [configuration composition](17-configuration-composition.md) for
cases where empty imported namespaces matter.

## Expand shared files in source order

`using` inserts another file's definitions at the declaration position. Start
its target with `f"{__dir__}/..."` to identify that file's directory explicitly.
Later same-name declarations
replace values while retaining every occurrence in `Config.history`.

<!-- lclang-doc-case: shared-pricing -->

`shared.lclcfg`:

<!-- lclang-doc-file: shared.lclcfg -->
```lclcfg
discount_rate: 0.05 # Base discount
shipping: 8 # Flat shipping charge
currency: "USD"
```

`application.lclcfg`:

<!-- lclang-doc-file: application.lclcfg -->
```lclcfg
using f"{__dir__}/shared.lclcfg"
discount_rate: 0.10 # Application discount

subtotal: unit_price * quantity
total: subtotal * (1 - discount_rate) + shipping
label: f"{currency} {total:.2f}"
```

Run this Python program beside the files:

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config


async def main() -> None:
    config = await load_config("application.lclcfg")
    assert len(config.history["discount_rate"]) == 2
    async with config.to_frame(preset={"unit_price": 25, "quantity": 4}) as frame:
        print(await frame.get("label"))
        assert await frame.get("total") == 98.0


asyncio.run(main())
```

The subtotal is `100`. The final discount rate is `0.10`, so the discounted
subtotal is `90`; shipping brings it to `98`. The program prints:

<!-- lclang-doc-output: stdout -->
```text
USD 98.00
```
<!-- /lclang-doc-case -->

The second `get` reuses the cached total. `config.to_frame(preset=...)` creates
a fresh caller-owned Frame synchronously; `async with` closes its owned state.
Configuration definitions normally take precedence over preset values.

## Allow an absent local file

Use `using?` when a deployment may omit a local override file. The question mark
must immediately follow the keyword. Only a directly missing target is skipped.
An existing file's read, decoding, syntax, nested dependency, or cycle error
continues to fail loading.

<!-- lclang-doc-case: absent-local-file -->

The local override file is absent in this example.

`application.lclcfg`:

<!-- lclang-doc-file: application.lclcfg -->
```lclcfg
discount_rate: 0.05
using? f"{__dir__}/local.lclcfg"
total: 100 * (1 - discount_rate)
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config


async def main() -> None:
    config = await load_config("application.lclcfg")
    assert len(config.history["discount_rate"]) == 1
    async with config.to_frame() as frame:
        print(await frame.get("total"))


asyncio.run(main())
```

The absent file contributes no definition or history. The base rate remains
`0.05`, and the program prints:

<!-- lclang-doc-output: stdout -->
```text
95.0
```
<!-- /lclang-doc-case -->

If `local.lclcfg` contains `discount_rate: 0.10`, it contributes a second history
entry and changes the total to `90.0`. A reused loader retries absent targets;
successful files keep their cached snapshots.

## Choose a file from preceding values

A dynamic target must be an f-string producing a nonempty `.lclcfg` path. It
reads definitions available before that introduction. A later declaration does
not change a target already selected.

<!-- lclang-doc-case: profile-selection -->

`profiles/production.lclcfg`:

<!-- lclang-doc-file: profiles/production.lclcfg -->
```lclcfg
service_name: "production"
```

`profiles/development.lclcfg`:

<!-- lclang-doc-file: profiles/development.lclcfg -->
```lclcfg
service_name: "development"
```

`application.lclcfg`:

<!-- lclang-doc-file: application.lclcfg -->
```lclcfg
profile: "production"
using f"{__dir__}/profiles/{profile}.lclcfg"
profile: "development"
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config


async def main() -> None:
    config = await load_config("application.lclcfg")
    async with config.to_frame() as frame:
        print(await frame.get("service_name"), await frame.get("profile"))


asyncio.run(main())
```

Loading selects the production file. Final runtime winners still include the
later development profile, so the two values differ:

<!-- lclang-doc-output: stdout -->
```text
production development
```
<!-- /lclang-doc-case -->

## Use explicit environment overrides

`env.NAME` reads the live process environment, and `??` provides an absent-value
fallback. Scoped loading overrides can select another file without changing the
process environment.

<!-- lclang-doc-case: environment-selection -->

`application.lclcfg`:

<!-- lclang-doc-file: application.lclcfg -->
```lclcfg
using f"{__dir__}/{env.LCLANG_TUTORIAL_PROFILE ?? 'local'}.lclcfg"
```

`local.lclcfg`:

<!-- lclang-doc-file: local.lclcfg -->
```lclcfg
profile_name: "local"
```

`blue.lclcfg`:

<!-- lclang-doc-file: blue.lclcfg -->
```lclcfg
profile_name: "blue"
```

`green.lclcfg`:

<!-- lclang-doc-file: green.lclcfg -->
```lclcfg
profile_name: "green"
```

<!-- lclang-doc-exec -->
```python
import asyncio
import os
from unittest.mock import patch

from lclang.config import load_config


async def main() -> None:
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LCLANG_TUTORIAL_PROFILE", None)
        for overrides in (None, None, {"env.LCLANG_TUTORIAL_PROFILE": "green"}):
            config = await load_config("application.lclcfg", overrides=overrides)
            async with config.to_frame() as frame:
                print(await frame.get("profile_name"))
            os.environ["LCLANG_TUTORIAL_PROFILE"] = "blue"
        assert os.environ["LCLANG_TUTORIAL_PROFILE"] == "blue"


asyncio.run(main())
```

The fallback chooses local, the process value chooses blue, and the explicit
loading override chooses green. Loading overrides do not become final runtime
configuration values. The program prints:

<!-- lclang-doc-output: stdout -->
```text
local
blue
green
```
<!-- /lclang-doc-case -->

## Reuse construction policy with fresh caches

Use `Config.frame_factory()` when several independent runs share one loaded
configuration. Each created Frame receives its own result and failure snapshots.

<!-- lclang-doc-case: independent-runs -->

`policy.lclcfg`:

<!-- lclang-doc-file: policy.lclcfg -->
```lclcfg
total: unit_price * quantity
origin: __file__
```

<!-- lclang-doc-exec -->
```python
import asyncio
from pathlib import Path

from lclang.config import load_config
from lclang.lang.runtime import Preset


async def main() -> None:
    config = await load_config("policy.lclcfg")
    factory = config.frame_factory(preset=Preset("pricing inputs", {"unit_price": 12, "quantity": 4}))
    async with factory.create() as first, factory.create(values={"quantity": 5}) as second:
        print(await first.get("total"), await second.get("total"))
        assert Path(str(await first.get("origin"))).name == "policy.lclcfg"


asyncio.run(main())
```

The first run uses four units and the second uses five. File magic retains the
defining physical file, and separate Frames prevent shared result caches:

<!-- lclang-doc-output: stdout -->
```text
48 60
```
<!-- /lclang-doc-case -->

Files decode as UTF-8, with a BOM accepted at byte zero. Loading performs no
globbing or network access. Use `ConfigLoadLimits` and an allowed-root resolver
when the application needs bounded loading. Treat configuration and supplied
Python objects as trusted code.

[Previous: The LCL language](03-language.md) | [Next: Async Python integration](05-async-python-integration.md) | [Return to the series introduction](README.md)
