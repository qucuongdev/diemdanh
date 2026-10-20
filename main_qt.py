"""Compatibility launcher. Run python main.py for normal use."""

import sys
from main import MainWindow, MainAppWidget, main

__all__ = ["MainWindow", "MainAppWidget", "main"]

if __name__ == "__main__":
    sys.exit(main())
