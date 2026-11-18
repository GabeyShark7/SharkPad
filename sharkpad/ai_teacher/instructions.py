import re
from dataclasses import dataclass

MARKER_RE = re.compile(r"AI-INSTRUCT\{(?:\$(.*?)\$|([^{}]*))\}[ \t]*;?", re.S)
START_TEMPLATE = "AI-INSTRUCT{$  $};"
END_MARKER = "AI-INSTRUCT{END};"


@dataclass
class Block:
    start: int
    end: int
    body_start: int
    body_end: int
    instruction: str
    body: str
    full_text: str


def _markers(text):
    for m in MARKER_RE.finditer(text):
        inside = m.group(1) if m.group(1) is not None else m.group(2)
        yield m, inside.strip()


def find_blocks(text):
    blocks, open_marker = [], None

    def close(end_start, end_end):
        m, instruction = open_marker
        body_start, body_end = m.end(), end_start
        blocks.append(Block(m.start(), end_end, body_start, body_end, instruction,
                            text[body_start:body_end].strip("\n"), text[m.start():end_end]))

    for m, inside in _markers(text):
        if inside.upper() == "END":
            if open_marker:
                close(m.start(), m.end())
                open_marker = None
            continue
        if open_marker:
            close(m.start(), m.start())
        open_marker = (m, inside)
    if open_marker:
        close(len(text), len(text))
    return blocks


def marker_spans(text):
    return [(m.start(), m.end()) for m, _inside in _markers(text)]
