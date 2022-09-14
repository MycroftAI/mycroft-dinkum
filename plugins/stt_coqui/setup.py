#!/usr/bin/env python3
from pathlib import Path

import setuptools
from setuptools import setup

this_dir = Path(__file__).parent
module_dir = this_dir / "mycroft_coqui"

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

model_dir = module_dir / "models" / "english_v1.0.0-large-vocab"
model_files = [str(p.relative_to(module_dir)) for p in model_dir.rglob("*")]

# -----------------------------------------------------------------------------

PLUGIN_ENTRY_POINT = "coqui_stt_plug = mycroft_coqui:CoquiStreamingSTT"

setup(
    name="mycroft_coqui",
    version=version,
    author="Mycroft AI",
    author_email="dev@mycroft.ai",
    description="Speech to text using Coqui STT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    packages=setuptools.find_packages(),
    package_data={"mycroft_coqui": ["VERSION", "py.typed"] + model_files},
    entry_points={"mycroft.plugin.stt": PLUGIN_ENTRY_POINT},
    keywords=["mycroft", "coqui", "stt"],
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
