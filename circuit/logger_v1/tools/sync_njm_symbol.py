"""Synchronize the reusable NJM2845 symbol with its verified schematic cache."""

from pathlib import Path


def block_end(text: str, start: int) -> int:
    depth = 0
    quoted = escaped = False
    for pos in range(start, len(text)):
        char = text[pos]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return pos + 1
    raise ValueError("unterminated S-expression")


root = Path(__file__).resolve().parents[1]
schematic = (root / "logger_v1.kicad_sch").read_text(encoding="utf-8")
library_path = root / "logger_v1_custom.kicad_sym"
library = library_path.read_text(encoding="utf-8")

schematic_marker = '(symbol "logger_v1_custom:NJM2845DL1-05"'
schematic_start = schematic.index(schematic_marker)
schematic_end = block_end(schematic, schematic_start)
symbol = schematic[schematic_start:schematic_end].replace(
    schematic_marker, '(symbol "NJM2845DL1-05"', 1
)

library_marker = '(symbol "NJM2845DL1-05"'
library_start = library.index(library_marker)
library_end = block_end(library, library_start)
library_path.write_text(
    library[:library_start] + symbol + library[library_end:],
    encoding="utf-8",
    newline="\n",
)
