"""Details of colors and styles."""

keyword_to_code = {}
keyword_colors = {
    'a': 'magenta',
    'b': 'chartreuse3',
    'c': 'blue_violet',
    'd': 'dark_goldenrod',
}
codes = sorted(keyword_colors)


def keyword_code(keyword):
    """Work out the numeric code for a given keyword."""
    n = keyword_to_code.get(keyword, 0)
    n = n % len(codes)
    return codes[n]


def add_keyword(keyword):
    """Add a keyword to the application's set."""
    if keyword in keyword_to_code:
        return
    keyword_to_code[keyword] = len(keyword_to_code)
