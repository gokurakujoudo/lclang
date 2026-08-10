# M097: boolean overrides and evaluated CLI inspection

## Goal

Allow a CLI override key to stand alone as boolean `True`, prevent a following
override option from being consumed as the preceding value, and let
`parse_lcl -o EVAL` evaluate `RESULT` before rendering its inspection tree.

## Module and test layout

- Override token boundaries remain pure parsing behavior in
  `pylcl/cli/parser.py`; the immutable value contract remains in
  `pylcl/cli/models.py` and Frame conversion remains in `pylcl/cli/binding.py`.
- Built-in command policy remains in `pylcl/cli/application.py`.
- Parser, model, binding, and executable command behavior are tested in their
  mirrored files under `tests/cli/`. All command arguments are static test data.

## Contract

- `-o|--override <key>` is valid at end of input and stores the exact Python
  boolean `True` for that key.
- If the token after an override key is `-o` or `--override`, the current key is
  stored as `True` and that token begins the next override. Therefore an
  override value can never be either override-option spelling.
- Any other following token remains the exact string value, including `-h`,
  `--literal`, empty text, and other option-looking text in the fixed value slot.
  Existing right-biased duplicate behavior, reserved-name checks, lazy
  `LCL[...]` detection, and malformed-marker literal behavior remain unchanged.
- A trailing `-o` without a key remains a typed CLI usage error. An override key
  still must be a non-reserved LCL identifier.
- `CliParams.overrides` is a detached read-only mapping of strings to either raw
  strings or the exact boolean `True`. Direct construction rejects `False` and
  every other value type. Binding stores boolean overrides as external host
  values and applies lazy-marker parsing only to strings.
- `parse_lcl` documents optional boolean parameter `EVAL`, defaulting to `False`.
  With no effective `EVAL=True`, inspection remains completely non-evaluating.
  With `EVAL=True`, it awaits `frame.get("RESULT")` before inspection.
- Successful evaluated inspection shows cached `RESULT` and any evaluated lazy
  dependencies with their values. If evaluation raises an ordinary exception,
  `parse_lcl` still renders the post-failure cached tree successfully so the
  structured error and variable evaluation stack remain inspectable. Process
  control exceptions continue to propagate.
- `eval_lcl` does not declare or interpret `EVAL`; an undeclared `-o EVAL` is
  still an ordinary available override under the framework's open binding
  model.

## TDD matrix

- Sunny: parse `-o EVAL`, bind it as external boolean `True`, and inspect a
  successful `RESULT` as `Cached` with its computed typed value.
- Rainy: reject trailing option-without-key, `False`/non-string direct override
  values, and prove `-o`/`--override` cannot become values; evaluate a failing
  result and render its cached structured failure rather than losing the tree.
- Composite-complex: mix valueless, literal, lazy, duplicate, and option-looking
  overrides; prove right bias, exact raw values, lazy evaluation, cached
  dependency states, no default evaluation, and unchanged `eval_lcl` output.

## Completion evidence

Record focused RED/GREEN commands, exact unevaluated/evaluated/failure tree
outputs, full quality results, and the verification date in `progress.md` before
marking this milestone DONE.
