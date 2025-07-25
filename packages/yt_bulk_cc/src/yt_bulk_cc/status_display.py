"""Dynamic status display using Rich Live for yt_bulk_cc."""

from __future__ import annotations

import logging
from typing import Optional

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class StatusDisplay:
    """Dynamic status display that updates in place using Rich Live."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.live_display: Optional[Live] = None
        self.status_message = "Initializing..."
        self.downloads_count = 0
        self.successful_downloads = 0
        self.total_videos = 0
        self.concurrent_jobs = 1
        self.proxies_in_use: list[str] = []
        self.active_proxy_count = 0
        self.proxies_used_count = 0
        self.no_caption_count = 0
        self.failed_count = 0
        self.proxy_fail_count = 0
        self.banned_count = 0
        self.progress: Optional[Progress] = None
        self.progress_task = None
        self._active = False
        
    def start(self) -> None:
        """Start the dynamic status display."""
        if not RICH_AVAILABLE:
            return
            
        try:
            # Create progress bar
            self.progress = Progress(
                SpinnerColumn(),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=self.console,
            )
            
            # Start live display
            self.live_display = Live(
                self._generate_display(),
                console=self.console,
                refresh_per_second=4,
                auto_refresh=True
            )
            self.live_display.start()
            self._active = True
            
        except Exception as e:
            logging.debug("Failed to start status display: %s", e)
            self._active = False
    
    def stop(self) -> None:
        """Stop the dynamic status display."""
        if self.live_display and self._active:
            try:
                self.live_display.stop()
                self._active = False
            except Exception as e:
                logging.debug("Error stopping status display: %s", e)
    
    def update_status(self, message: str) -> None:
        """Update the current status message."""
        self.status_message = message
        self._refresh_display()
    
    def update_downloads(self, count: int, total: Optional[int] = None) -> None:
        """Update the download progress."""
        self.downloads_count = count
        if total is not None:
            self.total_videos = total
            
        # Update progress bar if available
        if self.progress and self.progress_task is not None:
            try:
                self.progress.update(self.progress_task, completed=count)
            except Exception:
                pass
                
        self._refresh_display()
    
    def update_successful_downloads(self, count: int) -> None:
        """Update the successful downloads counter."""
        self.successful_downloads = count
        self._refresh_display()
    
    def update_jobs(self, count: int) -> None:
        """Update the concurrent jobs count."""
        self.concurrent_jobs = count
        self._refresh_display()
    
    def update_proxies(self, proxies: list[str]) -> None:
        """Update the list of proxies in use."""
        self.proxies_in_use = proxies[:10]  # Limit to first 10 for display
        self._refresh_display()
    
    def update_active_proxy_count(self, count: int) -> None:
        """Update the count of currently active/working proxies."""
        self.active_proxy_count = count
        self._refresh_display()
    
    def update_proxies_used_count(self, count: int) -> None:
        """Update the count of proxies that have been used."""
        self.proxies_used_count = count
        self._refresh_display()

    def update_counts(
        self,
        no_caption: int,
        failed: int,
        proxy_failed: int,
        banned: int,
    ) -> None:
        """Update download outcome counts."""
        self.no_caption_count = no_caption
        self.failed_count = failed
        self.proxy_fail_count = proxy_failed
        self.banned_count = banned
        self._refresh_display()
    
    def set_total_videos(self, total: int) -> None:
        """Set the total number of videos and create progress task."""
        self.total_videos = total
        if self.progress:
            try:
                self.progress_task = self.progress.add_task(
                    "Progress: Downloading", 
                    total=total,
                    completed=0
                )
            except Exception:
                pass
        self._refresh_display()
    
    def _generate_display(self) -> Panel:
        """Generate the display content."""
        if not RICH_AVAILABLE:
            return Panel("Status display unavailable")
            
        try:
            # Create main status table with proper alignment
            table = Table.grid(padding=(0, 1))
            table.add_column(style="bold blue", width=25)  # Fixed width for labels
            table.add_column()
            
            # Status line
            table.add_row("Status:", self.status_message)
            table.add_row("", "")  # Spacing
            
            # === DOWNLOAD METRICS ===
            # Downloads progress
            if self.total_videos > 0:
                progress_text = f"{self.downloads_count}/{self.total_videos}"
                percentage = (self.downloads_count / self.total_videos) * 100
                table.add_row("📊 Transcripts Processed:", f"{progress_text} ({percentage:.1f}%)")
            else:
                table.add_row("📊 Transcripts Processed:", str(self.downloads_count))
            
            # Successful downloads
            table.add_row("✅ Successful Downloads:", str(self.successful_downloads))
            
            # Concurrent jobs
            table.add_row("⚡ Concurrent Jobs:", str(self.concurrent_jobs))
            table.add_row("", "")  # Spacing

            # === PROXY METRICS ===
            # Active proxies count
            table.add_row("🌐 Active Proxies:", str(self.active_proxy_count))
            table.add_row("🔄 Proxies Used:", str(self.proxies_used_count))
            table.add_row("🚫 Proxies Banned:", str(self.banned_count))

            # Proxies list (limited)
            if self.proxies_in_use:
                proxy_text = Text()
                for i, proxy in enumerate(self.proxies_in_use):
                    if i > 0:
                        proxy_text.append("\n")
                    proxy_text.append(f"  • {proxy}", style="dim")
                table.add_row("   Proxy List:", proxy_text)
            
            table.add_row("", "")  # Spacing

            # === FAILURE METRICS ===
            table.add_row("↯ No Captions:", str(self.no_caption_count))
            table.add_row("⚠ Failed Downloads:", str(self.failed_count))
            table.add_row("🌐 Proxy Failures:", str(self.proxy_fail_count))
            
            # Progress bar
            content = [table]
            if self.progress and self.progress_task is not None:
                content.append(self.progress)

            try:
                from rich.console import Group

                renderable = Group(*content)
            except Exception:
                renderable = "\n".join(str(item) for item in content)

            return Panel(
                renderable,
                title="[bold blue]Download Status[/bold blue]",
                border_style="blue",
            )
            
        except Exception as e:
            logging.debug("Error generating display: %s", e)
            return Panel(f"Status: {self.status_message}")
    
    def _refresh_display(self) -> None:
        """Refresh the live display."""
        if self.live_display and self._active:
            try:
                self.live_display.update(self._generate_display())
            except Exception as e:
                logging.debug("Error refreshing display: %s", e)


# Fallback class for when Rich is not available
class FallbackStatusDisplay:
    """Fallback status display that just logs status updates."""
    
    def __init__(self, console=None):
        pass
    
    def start(self) -> None:
        pass
    
    def stop(self) -> None:
        pass
    
    def update_status(self, message: str) -> None:
        logging.info("Status: %s", message)
    
    def update_downloads(self, count: int, total: Optional[int] = None) -> None:
        if total:
            logging.info("Downloads: %d/%d", count, total)
        else:
            logging.info("Downloads: %d", count)
    
    def update_jobs(self, count: int) -> None:
        pass
    
    def update_proxies(self, proxies: list[str]) -> None:
        if proxies:
            logging.info("Using %d proxies", len(proxies))
    
    def update_active_proxy_count(self, count: int) -> None:
        """Update the count of currently active/working proxies."""
        logging.info("Active proxies: %d", count)
    
    def update_proxies_used_count(self, count: int) -> None:
        """Update the count of proxies that have been used."""
        logging.info("Proxies used: %d", count)

    def update_counts(
        self,
        no_caption: int,
        failed: int,
        proxy_failed: int,
        banned: int,
    ) -> None:
        logging.info(
            "Counts - no_caption=%d failed=%d proxy_failed=%d banned=%d",
            no_caption,
            failed,
            proxy_failed,
            banned,
        )
    
    def set_total_videos(self, total: int) -> None:
        logging.info("Processing %d videos", total)


def create_status_display(console=None) -> StatusDisplay | FallbackStatusDisplay:
    """Create a status display, falling back to simple logging if Rich is unavailable."""
    if RICH_AVAILABLE:
        return StatusDisplay(console)
    else:
        return FallbackStatusDisplay(console)