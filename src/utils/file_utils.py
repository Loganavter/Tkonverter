"""
File utilities.
"""

import os
import re

def get_unique_filepath(directory: str, base_name: str, extension: str) -> str:
    """
    Generates unique filename in specified directory.

    If file with such name already exists, adds counter in brackets to the name.

    Args:
        directory: Directory for file
        base_name: Base filename (without extension)
        extension: File extension (including dot)

    Returns:
        str: Full path to unique file

    Example:
        get_unique_filepath("/tmp", "document", ".txt")
        # Returns "/tmp/document.txt" or "/tmp/document (1).txt" if file exists
    """

    base_name = os.path.splitext(base_name)[0]

    full_path = os.path.join(directory, f"{base_name}{extension}")

    if not os.path.exists(full_path):
        return full_path

    counter = 1
    while True:

        clean_base = re.sub(r" \(\d+\)$", "", base_name)
        new_name = f"{clean_base} ({counter})"
        new_path = os.path.join(directory, f"{new_name}{extension}")

        if not os.path.exists(new_path):
            return new_path
        counter += 1
