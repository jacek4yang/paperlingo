"""PaperLingo：把论文中没看懂的英文拆开讲明白。"""

__version__ = "0.1.0"


def main() -> None:
    """入口：启动 Qt 应用。"""
    from paperlingo.app import run

    raise SystemExit(run())
