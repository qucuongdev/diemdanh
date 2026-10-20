"""Compatibility entry point for the PySide6-only offline benchmark."""

from benchmark import main

if __name__ == "__main__":
    raise SystemExit(main())
