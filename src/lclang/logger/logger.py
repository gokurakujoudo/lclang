"""Lightweight scope-independent wrappers using stdlib caller attribution."""

from __future__ import annotations

import logging
from typing import Any

from lclang.logger.context import current_runtime
from lclang.logger.formatter import PREFIX_ATTRIBUTE


class Logger:
    """Bind only a stdlib source name, prefix, and caller offset."""

    def __init__(self, name: str | None, prefix: str, emit_level: int) -> None:
        """Retain wrapper settings without owning a runtime or handlers.

        :param name: Stdlib source name; None selects root.
        :param prefix: Text inserted once at formatting time.
        :param emit_level: Additional application wrapper frames to skip.
        """
        self.backend = logging.getLogger(name)
        self.prefix, self.emit_level = prefix, emit_level

    @property
    def name(self) -> str:
        """Return the stdlib source name.

        :returns: Registered source name.
        """
        return self.backend.name

    def isEnabledFor(self, level: int) -> bool:
        """Check scope admission and the stdlib logger threshold.

        :param level: Candidate severity.
        :returns: Whether a producer should construct the event.
        """
        return not current_runtime().handler.closing and self.backend.isEnabledFor(level)

    def log(self, level: int, msg: object, *args: object, **kwargs: Any) -> None:
        """Forward a record with prefix metadata and adjusted stacklevel.

        :param level: Numeric severity.
        :param msg: Stdlib message object or formatting template.
        :param args: Deferred message formatting arguments.
        :param kwargs: Stdlib extra, exception and caller options.
        """
        runtime = current_runtime()
        with runtime.handler.admission:
            if runtime.handler.closing:
                return
            extra = dict(kwargs.pop("extra", None) or {})
            extra[PREFIX_ATTRIBUTE] = self.prefix
            stacklevel = kwargs.pop("stacklevel", 1) + self.emit_level + 1
            self.backend.log(level, msg, *args, extra=extra, stacklevel=stacklevel, **kwargs)

    def debug(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Emit DEBUG through the shared forwarding path.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param kwargs: Stdlib logging options.
        """
        self.log(logging.DEBUG, msg, *args, stacklevel=kwargs.pop("stacklevel", 1) + 1, **kwargs)

    def info(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Emit INFO through the shared forwarding path.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param kwargs: Stdlib logging options.
        """
        self.log(logging.INFO, msg, *args, stacklevel=kwargs.pop("stacklevel", 1) + 1, **kwargs)

    def warning(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Emit WARNING through the shared forwarding path.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param kwargs: Stdlib logging options.
        """
        self.log(logging.WARNING, msg, *args, stacklevel=kwargs.pop("stacklevel", 1) + 1, **kwargs)

    def error(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Emit ERROR through the shared forwarding path.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param kwargs: Stdlib logging options.
        """
        self.log(logging.ERROR, msg, *args, stacklevel=kwargs.pop("stacklevel", 1) + 1, **kwargs)

    def critical(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Emit CRITICAL through the shared forwarding path.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param kwargs: Stdlib logging options.
        """
        self.log(logging.CRITICAL, msg, *args, stacklevel=kwargs.pop("stacklevel", 1) + 1, **kwargs)

    def exception(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Emit ERROR with the current exception unless explicitly overridden.

        :param msg: Message object or template.
        :param args: Deferred formatting arguments.
        :param kwargs: Stdlib logging options including optional exc_info.
        """
        kwargs.setdefault("exc_info", True)
        self.log(logging.ERROR, msg, *args, stacklevel=kwargs.pop("stacklevel", 1) + 1, **kwargs)
