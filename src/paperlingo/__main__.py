"""允许 `python -m paperlingo` 启动。"""

from paperlingo.app import run

if __name__ == "__main__":
    raise SystemExit(run())
