"""Domain-specific exceptions."""


class SiteDownloaderError(Exception):
    """Base class for all site-downloader errors."""


class InvalidURL(SiteDownloaderError):
    """URL did not start with http/https or could not be parsed."""


class PandocMissing(SiteDownloaderError):
    """Pandoc executable is required for docx/epub output."""


class RenderFailure(SiteDownloaderError):
    """Playwright failed while capturing the page."""
