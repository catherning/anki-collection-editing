import re
from bs4 import BeautifulSoup


def extract_plain_text(html_content: str, transform_newline: bool = False) -> str:
    """Extracts clean plain text from HTML, preserving spacing or transforming newlines."""
    if not html_content:
        return ""
    
    # Replace common newline containers
    html_content = html_content.replace('\n', ' ')
    soup = BeautifulSoup(html_content, "html.parser")
    
    newline_replacement = " " if transform_newline else "\n"
    lines = []
    
    for element in soup.children:
        if isinstance(element, str):
            text = element.strip()
            if text:
                lines.append(text)
        elif element.name == 'br':
            lines.append(newline_replacement)
        else:
            if element.get_text(strip=True) == '':
                lines.append(newline_replacement)
            else:
                # Recursive call
                sub_lines = _extract_node_text(element, newline_replacement)
                lines.extend(sub_lines)
                
    lines = remove_pos_tags_from_lines(lines)
    return " ".join(lines)


def _extract_node_text(node, newline_replacement: str) -> list[str]:
    """Helper to recursively extract text from elements."""
    lines = []
    for element in node.children:
        if isinstance(element, str):
            text = element.strip()
            if text:
                lines.append(text)
        elif element.name == 'br':
            lines.append(newline_replacement)
        else:
            if element.get_text(strip=True) == '':
                lines.append(newline_replacement)
            else:
                lines.extend(_extract_node_text(element, newline_replacement))
    return lines


def remove_pos_tags_from_lines(lines: list[str]) -> list[str]:
    """Filters grammatical POS tags from extracted text lines."""
    pos_tags = {
        "ADJ", "ADJECTIVE", "ADP", "PUNCT", "ADV", "AUX", "SYM",
        "INTJ", "CCONJ", "NOUN", "DET", "PROPN", "NUM", "VERB",
        "PART", "PRON"
    }
    filtered = []
    for el in lines:
        if el not in pos_tags:
            filtered.append(el)
    if filtered and filtered[0] == "\n":
        filtered.pop(0)
    return filtered


def truncate_text(text: str, max_length: int = 30) -> str:
    """Safely extracts plain text and truncates it to a maximum length."""
    if not text:
        return ""
    plain = BeautifulSoup(text, "html.parser").text
    if len(plain) > max_length + 3:
        return plain[:max_length] + "..."
    return plain


def extract_cloze_deletion_text(html_text: str, cloze_deletion: str) -> str:
    """Extracts a specific cloze deletion from cloze formatted text.
    
    E.g. {{c1::hello}} -> "hello"
    """
    if not html_text:
        return ""
    # Regex pattern to match {{c1::content}}
    regex = r"\{\{%s::([^}:]*):?:?.*\}\}" % cloze_deletion
    p = re.compile(regex)
    m = p.search(html_text)
    if m:
        return m.group(1)
    else:
        # Fallback or error
        raise ValueError(f"Could not extract cloze deletion {cloze_deletion} from: {html_text}")


def breaklines_by_decade(sorted_hints: list[str]) -> list[str]:
    """Adds spacing entries between decades for chronological numerical values (years)."""
    if not sorted_hints:
        return []
    
    spaced_hints = []
    # Assumes hint format contains Year as first 4 digits, e.g. "1976 | Van Impe"
    # Or let's inspect the original character index:
    # note_hints_sorted[0][2]
    # Let's extract the first character of the sorting value or decadic prefix
    
    p = re.compile(r"(\d{4})")
    previous_decade = None
    
    for hint in sorted_hints:
        match = p.search(hint)
        if match:
            year = match.group(1)
            decade = year[:3]  # E.g. "197" for "1976"
            if previous_decade is not None and decade != previous_decade:
                spaced_hints.append("")  # Append a blank line separator
            previous_decade = decade
        spaced_hints.append(hint)
        
    return spaced_hints
