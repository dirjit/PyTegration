"""PyTegration — a teaching-grade FastAPI Task Manager + Claude agent.

LESSON: Module 1 (Python for Java Devs). See docs/01-python-for-java-devs.md
LAYER:  package root

WHAT IS THIS FILE?
    `__init__.py` marks a directory as an importable Python *package*. When
    Python imports `pytegration`, it executes this file.

JAVA NOTE:
    There is no exact Java equivalent. The closest idea is `package-info.java`
    combined with the fact that a Java package is just a directory on the
    classpath. In Python the directory PLUS this file is the package, and any
    code here runs on import — so we keep it tiny and side-effect-free.

SYNTAX TIP:
    `__name__` (dunder = "double underscore") variables are special, framework-
    level names. `__version__` is a widely-followed convention for exposing a
    package's version programmatically.
"""

# Single source of truth for the version at runtime. (The packaging version
# also lives in pyproject.toml; in a larger project you would derive one from
# the other to avoid drift.)
__version__ = "0.1.0"
