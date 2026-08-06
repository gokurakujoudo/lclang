# M047: standard-library manifests and namespace assembly

## Goal

Model reviewed standard-library exports as immutable ordered manifests and
assemble them into attribute-accessible namespaces consumable as a Preset,
without implementing concrete helpers yet.

## Module and test layout

- `pylcl/stdlib/manifest.py` owns immutable entry and manifest metadata.
- `pylcl/stdlib/namespaces.py` owns immutable mapping/attribute namespaces and
  deterministic Preset assembly.
- `pylcl/stdlib/__init__.py` exposes this standard-library construction API.
- `tests/stdlib/test_manifest.py` and `tests/stdlib/test_namespaces.py` mirror
  those production modules.

## Contract

- `StdlibEntry(name, value, summary)` requires a public, non-keyword Python/LCL
  identifier and non-blank one-line summary. It retains the opaque value by
  reference and never calls or awaits it.
- `StdlibManifest(namespace, entries)` requires the same identifier rules for
  its root namespace. Entries are copied into an immutable tuple in declaration
  order; duplicate entry names are rejected.
- `StdlibNamespace(namespace, members)` copies members into an insertion-ordered
  read-only mapping. It implements immutable `Mapping[str, object]`, attribute
  lookup for declared members, and a source-neutral `AttributeError` for absent
  members. Its own namespace name is diagnostic metadata.
- `assemble_stdlib(manifests, name="stdlib")` consumes its iterable once,
  preserves manifest order, rejects duplicate root namespaces, and returns a
  Preset mapping each manifest namespace to one `StdlibNamespace`.
- The preset name must be non-empty and is forwarded to Preset validation.
- Manifests and namespaces are detached from caller-owned entry sequences and
  mappings, but entry values remain shallow opaque references.
- Assembly performs no evaluation, call, await, import discovery, environment
  access, filesystem access, or network access. M048 supplies concrete reviewed
  zero-dependency helpers as ordinary manifest values.
- Public APIs use complete English rST documentation. Production and mirrored
  test modules stay below 200 physical lines.

## TDD evidence

RED requires imports from `pylcl.stdlib` to fail. GREEN requires identifier and
summary validation, duplicate rejection, immutable order/input detachment,
mapping and attribute lookup, opaque-reference retention, one-pass assembly,
duplicate namespace rejection, and direct evaluation through a Frame preset.
DONE requires the complete quality gate and synchronized bilingual
README/progress documentation.
