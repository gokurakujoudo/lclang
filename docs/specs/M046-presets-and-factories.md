# M046: immutable preset overlays and Frame factories

## Goal

Provide reusable immutable host-binding presets and a typed factory that creates
independent Frames with explicit, deterministic override precedence.

## Module and test layout

- `pylcl/runtime/presets.py` owns immutable named presets and shallow overlays.
- `pylcl/runtime/frame_factory.py` owns reusable Frame construction policy.
- `tests/runtime/test_presets.py` and `tests/runtime/test_frame_factory.py`
  mirror those production modules.

## Contract

- `Preset(name, values)` requires a non-empty name and non-empty binding keys.
  It copies the supplied mapping into an insertion-ordered read-only snapshot;
  referenced values themselves are retained without copying or awaiting.
- `preset.overlay(other, name=None)` returns a new Preset. `other` wins on key
  collisions, non-colliding bindings retain deterministic mapping order, and
  neither input changes. The explicit non-empty `name` is used when supplied;
  otherwise the stable name is `"<left>+<right>"`.
- Overlay is deliberately shallow. A mapped dictionary, awaitable, callable, or
  resource remains one opaque host value rather than being recursively merged.
- `FrameFactory(module, preset=None, limits=None)` retains immutable policy. It
  validates field types and never creates or caches a Frame during construction.
- `factory.with_preset(preset)` returns a new factory whose preset is the shallow
  overlay of the existing preset followed by `preset`; the original factory and
  presets remain unchanged. With no existing preset, the supplied immutable
  preset is retained directly.
- `factory.create(frame_id, values=None, parent=None, limits=None)` creates a new
  independent Frame. Call-level values override preset bindings. Call-level
  limits override factory limits; if neither exists, Frame defaults apply.
- Every call owns fresh caches, tasks, dependency traces, and lifecycle state.
  The supplied parent is borrowed exactly as with direct Frame construction.
- Direct Frame construction remains supported and behaviourally equivalent to
  creating through a factory with the same effective arguments.
- Public APIs use complete English rST documentation. Production and mirrored
  test modules stay below 200 physical lines.

## TDD evidence

RED requires `Preset` and `FrameFactory` public imports to fail. GREEN requires
validation, input detachment, read-only mapping, shallow precedence, stable
order/naming, factory immutability, call overrides, independent cache/lifecycle,
parent routing, and limit precedence. DONE requires the complete quality gate
and synchronized bilingual README/progress documentation.
