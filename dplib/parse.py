# DPLib - Asynchronous bot framework for Digital Paint: Paintball 2 servers
# Copyright (C) 2017  Michał Rokita
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
