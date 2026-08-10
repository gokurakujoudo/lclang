"""Public lexical values and scanning entry point."""

from lclang.lang.lexer.scanner import scan_tokens
from lclang.lang.lexer.tokens import Token, TokenKind

__all__ = ["Token", "TokenKind", "scan_tokens"]
