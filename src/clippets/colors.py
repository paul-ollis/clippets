"""Details of colors and styles."""
from __future__ import annotations

from collections import Counter


keyword_colors = {
    'a': 'bright_magenta',
    'b': 'deep_sky_blue1',
    'c': 'spring_green3',
    'd': 'light_sky_blue3',
    'e': 'deep_pink4',
    'f': 'dark_goldenrod',
    'g': 'dark_sea_green1',
    'h': 'yellow3',
    'i': 'pale_turquoise1',
    'j': 'dark_olive_green2',
}
codes = sorted(keyword_colors)


class KeywordTracker:
    """Tracks keywords and allocates colors to them."""

    def __init__(self):
        self.code_map: dict[str, str] = {}
        self.code_counts: Counter[str] = Counter(
            reversed(sorted(keyword_colors.keys())))

    def code(self, word):
        """Work out the numeric code for a given keyword."""
        return self.code_map.get(word, 'a')

    def add(self, word: str):
        """Add a keyword to the application's set."""
        if word not in self.code_map:
            code = self.code_counts.most_common()[-1][0]
            self.code_map[word] = code
            self.code_counts[code] += 1

    def apply_changes(self, new_words: set[str]):
        """Add new  keywords and remove dropped ones."""
        current = set(self.code_map)
        removed = current - new_words
        added = new_words - current
        for word in removed:
            code = self.code_map.pop(word)
            self.code_counts[code] -= 1
        for word in sorted(added):
            self.add(word)

    def reset(self):
        """Reset; for testing purposes."""
        self.code_map = {}
        self.code_counts = Counter(
            reversed(sorted(keyword_colors.keys())))


def reset_for_tests():
    """Perform a 'system' reset for test purposes.

    This is not intended for non-testing use.
    """
    keywords.reset()


keywords = KeywordTracker()
