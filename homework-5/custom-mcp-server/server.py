"""Custom MCP server exposing the contents of ``lorem-ipsum.md``.

It publishes the same word-limited text twice, through the two different MCP
primitives:

* a **resource** (``lorem://text`` and ``lorem://text/{word_count}``) — a URI the
  client reads from, like a file or an API endpoint;
* a **tool** (``read``) — an action the client invokes, which returns the very
  same content the resource serves.

Both accept a ``word_count`` parameter that defaults to 30, and both delegate to
:func:`_read_words` so the two primitives can never drift apart.
"""

from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("lorem-ipsum")

LOREM_PATH = Path(__file__).parent / "lorem-ipsum.md"
DEFAULT_WORD_COUNT = 30


def _read_words(word_count: int = DEFAULT_WORD_COUNT) -> str:
    """Return the first ``word_count`` whitespace-separated words of the file.

    If the file holds fewer words than requested, every available word is
    returned — the result is never padded.
    """
    if word_count < 0:
        raise ValueError(f"word_count must be zero or positive, got {word_count}")

    words = LOREM_PATH.read_text(encoding="utf-8").split()
    return " ".join(words[:word_count])


@mcp.resource("lorem://text")
def lorem_text() -> str:
    """The lorem ipsum text, trimmed to the default of 30 words."""
    return _read_words()


@mcp.resource("lorem://text/{word_count}")
def lorem_text_with_count(word_count: int) -> str:
    """The lorem ipsum text, trimmed to ``word_count`` words."""
    return _read_words(word_count)


@mcp.tool
def read(word_count: int = DEFAULT_WORD_COUNT) -> str:
    """Read the lorem ipsum text.

    Args:
        word_count: How many words to return. Defaults to 30.
    """
    return _read_words(word_count)


if __name__ == "__main__":
    # stdio transport: the process stays silent and waits for a client on stdin.
    mcp.run()
