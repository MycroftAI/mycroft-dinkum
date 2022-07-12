#!/usr/bin/env python3
from pathlib import Path

import setuptools
from setuptools import setup

this_dir = Path(__file__).parent
module_dir = this_dir / "hotword_precise_lite"

# -----------------------------------------------------------------------------

# Load README in as long description
long_description: str = ""
readme_path = this_dir / "README.md"
if readme_path.is_file():
    long_description = readme_path.read_text(encoding="UTF-8")

requirements = []
requirements_path = this_dir / "requirements.txt"
if requirements_path.is_file():
    with open(requirements_path, "r", encoding="utf-8") as requirements_file:
        requirements = requirements_file.read().splitlines()

version_path = module_dir / "VERSION"
with open(version_path, "r", encoding="utf-8") as version_file:
    version = version_file.read().strip()

# -----------------------------------------------------------------------------

PLUGIN_ENTRY_POINT = "precise = hotword_precise_lite:TFLiteHotWordEngine"

setup(
    name="hotword_precise_lite",
    version=version,
    author="Mycroft AI",
    author_email="dev@mycroft.ai",
    description="Precise wake word runner for Mycroft using Tensorflow Lite",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    packages=setuptools.find_packages(),
    package_data={
        "hotword_precise_lite": ["models/hey_mycroft.tflite", "VERSION", "py.typed"]
    },
    entry_points={"mycroft.plugin.wake_word": PLUGIN_ENTRY_POINT},
    keywords=["mycroft", "wake word", "hot word", "precise", "lite", "tensorflow"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
        "Topic :: Text Processing :: Linguistic",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    install_requires=requirements,
)
