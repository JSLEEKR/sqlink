"""SQL query formatter — pretty-print SQL with consistent style."""

from __future__ import annotations

import re


KEYWORDS_NEWLINE = {
    "SELECT", "FROM", "WHERE", "AND", "OR",
    "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN",
    "FULL JOIN", "CROSS JOIN", "LEFT OUTER JOIN", "RIGHT OUTER JOIN",
    "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "OFFSET",
    "UNION", "UNION ALL", "EXCEPT", "INTERSECT",
    "INSERT INTO", "VALUES", "UPDATE", "SET", "DELETE FROM",
    "ON", "USING",
}

KEYWORDS_UPPER = {
    "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN",
    "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS", "OUTER",
    "ON", "AS", "IS", "NULL", "LIKE", "BETWEEN", "EXISTS",
    "GROUP", "BY", "ORDER", "ASC", "DESC", "HAVING",
    "LIMIT", "OFFSET", "UNION", "ALL", "EXCEPT", "INTERSECT",
    "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE",
    "CREATE", "TABLE", "ALTER", "DROP", "INDEX",
    "DISTINCT", "CASE", "WHEN", "THEN", "ELSE", "END",
    "COUNT", "SUM", "AVG", "MIN", "MAX",
    "TRUE", "FALSE",
}


def format_sql(sql: str, *, indent: int = 2, uppercase: bool = True) -> str:
    """Format a SQL query with consistent indentation and keyword casing.

    Args:
        sql: The SQL query to format.
        indent: Number of spaces for indentation.
        uppercase: Whether to uppercase keywords.
    """
    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", sql.strip().rstrip(";"))
    if not normalized:
        return ""

    # Tokenize (preserve strings and identifiers)
    tokens = _tokenize(normalized)

    # Apply formatting
    lines: list[str] = []
    current_indent = 0
    current_line: list[str] = []

    i = 0
    while i < len(tokens):
        token = tokens[i]
        upper_token = token.upper()

        # Check for two-word keywords
        two_word = None
        if i + 1 < len(tokens):
            two_word = f"{upper_token} {tokens[i + 1].upper()}"

        # Handle two-word keywords
        if two_word in KEYWORDS_NEWLINE:
            if current_line:
                lines.append(" " * current_indent + " ".join(current_line))
                current_line = []

            keyword = two_word if uppercase else f"{token} {tokens[i + 1]}"
            if two_word in ("INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN",
                           "CROSS JOIN", "LEFT OUTER JOIN", "RIGHT OUTER JOIN"):
                current_line = [keyword]
            elif two_word in ("GROUP BY", "ORDER BY", "INSERT INTO", "DELETE FROM",
                             "UNION ALL"):
                current_line = [keyword]
            else:
                current_line = [keyword]
            i += 2
            continue

        # Handle single-word keywords that start new lines
        if upper_token in KEYWORDS_NEWLINE and upper_token not in ("AND", "OR", "ON"):
            if current_line:
                lines.append(" " * current_indent + " ".join(current_line))
                current_line = []
            current_line = [upper_token if uppercase else token]
            i += 1
            continue

        # AND/OR get new lines with indent
        if upper_token in ("AND", "OR"):
            if current_line:
                lines.append(" " * current_indent + " ".join(current_line))
                current_line = []
            current_line = [" " * indent + (upper_token if uppercase else token)]
            i += 1
            continue

        # ON for joins
        if upper_token == "ON":
            current_line.append(upper_token if uppercase else token)
            i += 1
            continue

        # Regular tokens
        if uppercase and upper_token in KEYWORDS_UPPER:
            current_line.append(upper_token)
        else:
            current_line.append(token)
        i += 1

    if current_line:
        lines.append(" " * current_indent + " ".join(current_line))

    result = "\n".join(lines)
    return result


def _tokenize(sql: str) -> list[str]:
    """Tokenize SQL preserving strings and identifiers."""
    tokens: list[str] = []
    i = 0
    current: list[str] = []

    while i < len(sql):
        char = sql[i]

        # String literal
        if char in ("'", '"'):
            if current:
                tokens.append("".join(current))
                current = []
            quote = char
            string_chars = [char]
            i += 1
            while i < len(sql):
                if sql[i] == "\\" and i + 1 < len(sql):
                    string_chars.append(sql[i])
                    string_chars.append(sql[i + 1])
                    i += 2
                elif sql[i] == quote:
                    string_chars.append(sql[i])
                    i += 1
                    break
                else:
                    string_chars.append(sql[i])
                    i += 1
            tokens.append("".join(string_chars))
            continue

        # Whitespace
        if char in (" ", "\t", "\n"):
            if current:
                tokens.append("".join(current))
                current = []
            i += 1
            continue

        # Operators and punctuation (keep as separate tokens)
        if char in ("(", ")", ",", ";"):
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(char)
            i += 1
            continue

        # Multi-char operators
        if char in ("<", ">", "!", "=") and i + 1 < len(sql) and sql[i + 1] == "=":
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(char + sql[i + 1])
            i += 2
            continue

        if char in ("<", ">"):
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(char)
            i += 1
            continue

        current.append(char)
        i += 1

    if current:
        tokens.append("".join(current))

    return tokens


def compact(sql: str) -> str:
    """Compact a SQL query to a single line."""
    return re.sub(r"\s+", " ", sql.strip().rstrip(";")).strip()
