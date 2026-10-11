"""Tree connectors for already protected, detached text.

Defines ``TextTree``, ``build_text_tree``, ``render_text_tree``, ``sort_display_name``.
"""

# Unitless recursive text pairs carry no runtime objects or language dependencies.
type TextTree = tuple[str, tuple[TextTree, ...]]


def build_text_tree(label: str, children: tuple[TextTree, ...] = ()) -> TextTree:
    """Construct a typed boundary for recursive tuple inference in both checkers.

    :param label: Already-protected node text.
    :param children: Ordered detached descendants.
    :returns: The final immutable text pair, without wrappers or runtime objects.
    """
    return label, children


def render_text_tree(tree: TextTree, *, prefix: str = "", connector: str = "") -> list[str]:
    """Render a detached text tree with shared branch connectors.

    :param tree: Protected label and ordered child pairs.
    :param prefix: Existing ancestor indentation.
    :param connector: Root connector, empty when the root stands alone.
    :returns: Physical lines with continuous ancestor branches.
    """
    label, children = tree
    continuation = prefix + ("│  " if connector == "├─ " else "   " if connector else "")
    parts = label.splitlines() or [""]
    lines = [prefix + connector + parts[0], *(continuation + part for part in parts[1:])]
    for index, child in enumerate(children):
        branch = "└─ " if index == len(children) - 1 else "├─ "
        lines.extend(render_text_tree(child, prefix=continuation, connector=branch))
    return lines


def sort_display_name(name: str) -> tuple[str, str]:
    """Choose deterministic alphabetical order without merging distinct names.

    :param name: Semantic name already obtained by the caller.
    :returns: Case-insensitive key followed by the exact spelling.
    """
    return name.casefold(), name
