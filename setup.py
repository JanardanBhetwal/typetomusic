"""
setup.py for TypeToMusic.
Supports: pip install -e .  and  python setup.py sdist bdist_wheel
"""

from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="typetomusic",
    version="1.0.0",
    description="Turn your keyboard into a musical instrument – real-time MIDI on every keystroke",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="TypeToMusic Contributors",
    python_requires=">=3.9",
    packages=find_packages(),
    install_requires=[
        "PyQt5>=5.15.0",
        "pynput>=1.7.6",
        "pyfluidsynth>=1.3.3",
    ],
    entry_points={
        "console_scripts": [
            "typetomusic=main:main",
        ],
        "gui_scripts": [
            "typetomusic-gui=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
        "Environment :: X11 Applications :: Qt",
        "Topic :: Multimedia :: Sound/Audio :: MIDI",
    ],
)
