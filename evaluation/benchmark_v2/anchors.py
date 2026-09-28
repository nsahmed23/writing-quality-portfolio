"""Resolve literal quotes to Python Unicode code-point spans."""


class AnchorError(ValueError):
    """A quote cannot be resolved; ``reason`` is a stable rejection code."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def resolve_anchor(
    text: str,
    quote: str,
    *,
    occurrence: int | None = None,
    left_context: str | None = None,
    right_context: str | None = None,
) -> tuple[int, int]:
    """Find one literal quote with optional one-based occurrence and adjacent context.

    Occurrences count overlapping matches before context is considered. The end
    offset is exclusive; both offsets use Python string indexes, not byte offsets.
    """
    if not isinstance(text, str):
        raise AnchorError("INVALID_TEXT")
    if not isinstance(quote, str):
        raise AnchorError("INVALID_QUOTE")
    if not quote:
        raise AnchorError("EMPTY_QUOTE")
    if occurrence is not None and (type(occurrence) is not int or occurrence < 1):
        raise AnchorError("INVALID_OCCURRENCE")
    if (left_context is not None and not isinstance(left_context, str) or
            right_context is not None and not isinstance(right_context, str)):
        raise AnchorError("INVALID_CONTEXT")

    starts = []
    position = text.find(quote)
    while position != -1:
        starts.append(position)
        position = text.find(quote, position + 1)

    if occurrence is not None:
        if occurrence > len(starts):
            raise AnchorError("OCCURRENCE_OUT_OF_RANGE")
        starts = [starts[occurrence - 1]]

    candidates = []
    for start in starts:
        end = start + len(quote)
        if left_context is not None and not text[:start].endswith(left_context):
            continue
        if right_context is not None and not text[end:].startswith(right_context):
            continue
        candidates.append((start, end))
    if not candidates:
        raise AnchorError("ANCHOR_NOT_FOUND")
    if len(candidates) != 1:
        raise AnchorError("AMBIGUOUS_ANCHOR")
    return candidates[0]
