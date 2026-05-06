"""程序入口"""

from .cli import get_config
from .tui import run_tui


def main():
    config = get_config()
    run_tui(config)


if __name__ == "__main__":
    main()
