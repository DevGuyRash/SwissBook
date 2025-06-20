"""Allow ``python -m site_downloader …``."""

from site_downloader.cli import app


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
