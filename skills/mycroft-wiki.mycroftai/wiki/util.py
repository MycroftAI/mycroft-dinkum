# Copyright 2021, Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re


def clean_text(input: str) -> str:
    """Clean Wikipedia text for presentation or speech.

    This removes common Wikipedia artifacts that are not required to provide a
    minimal yet complete answer. These include section headings, phonetic spellings, birth and
    death dates, etc.
    """
    # 1. REMOVE ARTIFACTS
    cleaned_text = remove_nested_parentheses(input)
    # Remove section headings
    cleaned_text = re.sub(r"={2,}.*?={2,}", "", cleaned_text)

    # 2. REFORMAT REMAINING TEXT
    # Remove duplicate white spaces
    cleaned_text = " ".join(cleaned_text.split()).strip()
    # Remove white space before comma - left by removal of other content
    cleaned_text = cleaned_text.replace(" , ", ", ")
    # Separate joined sentences eg "end of one.Start of another"
    # Only perform this when a new sentence starts with a capitalized word
    # will not catch sentences starting with single letters.
    cleaned_text = re.sub(r"\.([A-Z][a-z]+)", r". \1", cleaned_text)

    return cleaned_text


def remove_nested_parentheses(input: str) -> str:
    """Remove content contained within parentheses from a string.

    This includes content that is nested within multiple sets, eg:
    Lemurs (/ˈliːmər/ (listen) LEE-mər)
    """
    ret = ""
    nest_depth = 0
    for char in input:
        if char == "(":
            nest_depth += 1
        elif (char == ")") and nest_depth:
            nest_depth -= 1
        elif not nest_depth:
            ret += char
    return ret
