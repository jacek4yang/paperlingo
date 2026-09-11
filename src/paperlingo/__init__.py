"""PaperLingo: break down hard English paper sentences and explain them clearly."""

__version__ = "0.1.0"


def main() -> None:
    """Entry point: start the Qt application."""
    from paperlingo.app import run

    raise SystemExit(run())
