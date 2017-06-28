"""
A module for parsing DP data
"""


def render_text(text):
    """
    Renders some text with formatting to a DP message.
    Replaces {C} with color char (ASCII 136), {U} with underline (ASCII 134) and {I} with italic (ASCII 135)

    :param text: Text to render
    :type text: str

    :return: DP message
    :rtype: str
    """
    return text.format(C=chr(136), U=chr(134), I=chr(135))


def escape_braces(string):
    """
    Escapes braces, use for user-input in :func:`render_text`

    :param string: string to escape
    :return: escaped string
    """
    return string.replace('{', '{{').replace('}', '}}')
