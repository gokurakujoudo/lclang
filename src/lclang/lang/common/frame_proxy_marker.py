"""Frame proxy declaration marker.

Defines ``FrameProxyMarker``.
"""


class FrameProxyMarker:
    """Represent the singleton declaration value for a scoped prefix.

    .. note::
       Runtime proxies are separate caller-bound :class:`FrameProxy` values.
    """

    def __repr__(self) -> str:
        """Return the canonical LCL spelling.

        :returns: Stable proxy declaration source.
        """
        return "FRAME_PROXY"


# Unitless singleton identifies a declared binding prefix.
FRAME_PROXY = FrameProxyMarker()
