import io
from pathlib import Path
from typing import Iterable, Union

from fsticuffs.grammar import Grammar


def parse_ini_files(ini_paths: Iterable[Union[str, Path]]) -> Grammar:
    """Parse multiple Rhasspy Template Language files as a single combined file"""
    with io.StringIO() as combined_ini_file:
        for ini_path in ini_paths:
            with open(ini_path, "r", encoding="utf-8") as ini_file:
                for line in ini_file:
                    print(line, end="", file=combined_ini_file)

            # Blank line between files
            print("", file=combined_ini_file)

        # Parse as a single file
        combined_ini_file.seek(0)
        return Grammar.parse_file(combined_ini_file)
