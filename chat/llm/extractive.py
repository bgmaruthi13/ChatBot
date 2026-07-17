from .base import LLMProvider


class ExtractiveProvider(LLMProvider):
    """Default provider - no API key, no external call. Returns the
    top-ranked retrieved passages verbatim with page citations. This is
    a real, working answer mode (not a placeholder): until a generative
    provider is configured (Epic 9), this is what powers chat.
    """

    def generate(self, question, chunks):
        if not chunks:
            return (
                "I couldn't find anything in this document relevant to "
                f'"{question}".'
            )

        parts = [f"Here's what I found relevant to \"{question}\":"]
        for chunk in chunks:
            parts.append(f"\n\nFrom page {chunk['page_number']}:\n{chunk['text']}")
        return "".join(parts)
