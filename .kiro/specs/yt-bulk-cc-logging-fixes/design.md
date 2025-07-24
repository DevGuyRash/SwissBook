# Design Document

## Overview

This design addresses critical issues in the YouTube Bulk CC downloader's logging, console output, proxy management, and user experience. The solution involves refactoring the logging architecture to separate console and file outputs, implementing a dynamic status display using Rich, enhancing proxy visibility and management, and restoring emoji-based status indicators.

The design maintains backward compatibility while significantly improving the user experience through better visual feedback, clearer proxy status reporting, and proper separation of concerns between console and log outputs.

## Architecture

### Current Architecture Issues

1. **Logging Duplication**: Console prints are automatically captured by the log file through stdout/stderr redirection, causing duplicate entries
2. **Missing Visual Feedback**: Emojis were removed, making status less intuitive
3. **Poor Proxy Visibility**: Users can't see which proxies are being used or when they fail
4. **Static Output**: No dynamic status updates, causing screen clutter
5. **SwiftShadow Integration**: SwiftShadow logs are not properly captured

### New Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Entry Point                          │
│  - Argument parsing                                         │
│  - Initial setup                                           │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                 Logging Manager                             │
│  - Separate console and file handlers                      │
│  - SwiftShadow log capture                                 │
│  - Emoji restoration                                       │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│              Dynamic Status Display                         │
│  - Rich-based live updates                                 │
│  - Status, jobs, proxy list                               │
│  - Progress bar integration                                │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│               Proxy Manager                                 │
│  - Enhanced proxy tracking                                 │
│  - Rotation logging                                        │
│  - Failure reporting                                       │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│              Core Processing                                │
│  - Video downloading (unchanged)                           │
│  - Transcript processing (unchanged)                       │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Enhanced Logging System

**LoggingManager Class**
```python
class LoggingManager:
    def __init__(self, console_level: int, log_file: Path | None):
        self.console_handler: RichHandler
        self.file_handler: FileHandler | None
        self.swiftshadow_captured: bool
        
    def setup_handlers(self) -> None
    def capture_swiftshadow_logs(self) -> None
    def log_and_print_summary(self, summary_data: dict) -> None
    def restore_emoji_formatting(self) -> None
```

**Key Features:**
- Separate console and file logging streams
- SwiftShadow log capture through logger hierarchy
- Independent summary generation for console and log
- Emoji restoration in ColorFormatter

### 2. Dynamic Status Display

**StatusDisplay Class**
```python
class StatusDisplay:
    def __init__(self, console: Console):
        self.console: Console
        self.live_display: Live
        self.status_table: Table
        self.proxy_panel: Panel | None
        
    def start(self) -> None
    def update_status(self, message: str) -> None
    def update_downloads(self, count: int) -> None
    def update_jobs(self, count: int) -> None
    def update_proxies(self, proxies: list[str]) -> None
    def stop(self) -> None
```

**Dynamic Display Format (updates in place):**
```
Status: Processing video 3/5...
Transcripts Downloaded: 2
Proxies in use: 2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 60%
```

**Final Console Output Format:**
```
File statistics:
1. 00005 [_nAu9D-8srA] Learning Colors – Colorful Eggs on a Farm.json - 125 w · 73 l · 1,212 c
2. 00004 [FBzyUlSurj4] #toys #kidstoys #shorts #eggs #eggsonfarms #learrncolors.json - 145 w · 58 l · 1,169 c
...up to --summary-stats-top (renamed from --stats-top)

Videos without captions:
• https://youtu.be/RhJzbM-srlI — 🎉 3D Printed Dinosaur Surprise Toys + Color Cars! DIY Fun for Kids 🚗🦖
• https://youtu.be/uIGCavE8ozk — 🧸 3D Printed Surprise Toys for Kids! Fun Bunny Boxes & Shapes Inside
• https://youtu.be/5ZCv9Z--jgw — Magical 3D Printed Rainbow Eggs Just for You! Surprise Toys Inside!
• ...up to --summary-max-no-captions

Videos transcripts that failed to download:
• https://youtu.be/example1 — Example Failed Video 1
• https://youtu.be/example2 — Example Failed Video 2
...up to --summary-max-failed (only shows if there are failures)

Proxies Used:
• 192.168.1.1:8080
• 10.0.0.1:3128
• 203.0.113.1:1080
...up to --summary-max-proxies

Summary: ✓ 2   •  ↯ no-caption 3   •  ⚠ failed 0   🚫 proxies banned 0   (total 5)
```

**Log File Output:**
The same final output sections (File statistics, Videos without captions, etc.) should appear at the END of the log file as separate log entries, not as captured console prints. This ensures clean separation between console output and log entries.

### 3. Enhanced Proxy Management

**ProxyTracker Class**
```python
class ProxyTracker:
    def __init__(self):
        self.active_proxies: dict[str, ProxyInfo]
        self.banned_proxies: set[str]
        self.rotation_count: int
        
    def log_proxy_usage(self, proxy: str, video_id: str) -> None
    def log_proxy_failure(self, proxy: str, reason: str) -> None
    def log_proxy_rotation(self, old_proxy: str, new_proxy: str) -> None
    def get_active_proxy_list(self) -> list[str]
```

**ProxyInfo DataClass**
```python
@dataclass
class ProxyInfo:
    url: str
    usage_count: int
    last_used: datetime
    status: ProxyStatus
    failures: list[str]
```

### 4. Summary Generation System

**SummaryGenerator Class**
```python
class SummaryGenerator:
    def __init__(self, limits: SummaryLimits):
        self.limits: SummaryLimits
        
    def generate_console_summary(self, results: ProcessingResults) -> str
    def generate_log_summary(self, results: ProcessingResults) -> str
    def format_file_statistics(self, files: list[Path]) -> str
    def format_proxy_usage(self, proxies: list[str]) -> str
```

**SummaryLimits Configuration**
```python
@dataclass
class SummaryLimits:
    stats_top: int = 10  # --summary-stats-top
    max_no_captions: int = 20  # --summary-max-no-captions  
    max_failed: int = 20  # --summary-max-failed
    max_proxies: int = 10  # --summary-max-proxies
```

## Data Models

### ProcessingResults
```python
@dataclass
class ProcessingResults:
    successful: list[VideoResult]
    no_captions: list[VideoResult]
    failed: list[VideoResult]
    proxy_failed: list[VideoResult]
    banned_proxies: set[str]
    active_proxies: list[str]
    file_stats: list[FileStats]
```

### VideoResult
```python
@dataclass
class VideoResult:
    video_id: str
    title: str
    url: str
    status: str
    proxy_used: str | None = None
    error_message: str | None = None
```

### FileStats
```python
@dataclass
class FileStats:
    path: Path
    words: int
    lines: int
    chars: int
    video_id: str
    title: str
```

## Error Handling

### Console Error Suppression
- Wrap urllib3 connection cleanup in try/catch
- Suppress finalize object errors during shutdown
- Provide graceful fallbacks for Rich display failures
- Handle SwiftShadow import/initialization errors

### Proxy Error Management
- Implement exponential backoff for proxy failures
- Clear proxy ban logging with specific reasons
- Graceful degradation when all proxies are banned
- Validation error handling with fallback to direct connection

### Cache Error Handling
- Detect and handle cache invalidation properly
- Provide clear logging when cache operations fail
- Implement fallback behavior for cache-related errors

## Testing Strategy

### Unit Tests
1. **LoggingManager Tests**
   - Verify console/log separation
   - Test SwiftShadow log capture
   - Validate emoji restoration

2. **StatusDisplay Tests**
   - Mock Rich components
   - Test dynamic updates
   - Verify proxy list display

3. **ProxyTracker Tests**
   - Test proxy rotation logging
   - Verify failure tracking
   - Validate usage statistics

4. **SummaryGenerator Tests**
   - Test output formatting
   - Verify limit enforcement
   - Test emoji integration

### Integration Tests
1. **Proxy Integration Tests**
   - Test --proxy flag functionality
   - Test --proxy-file functionality
   - Verify custom proxy precedence
   - Test public proxy integration

2. **Logging Integration Tests**
   - Verify log/console separation
   - Test SwiftShadow log capture
   - Validate summary generation

3. **End-to-End Tests**
   - Test complete workflow with proxies
   - Verify dynamic display functionality
   - Test error handling scenarios

### Test Data Requirements
- Mock proxy servers for testing
- Sample YouTube URLs for integration tests
- Test proxy files with various formats
- Mock SwiftShadow responses

## Implementation Considerations

### Rich Integration
- Use Rich's Live display for dynamic updates
- Implement proper console detection for terminal features
- Provide fallback for non-terminal environments
- Handle Rich import failures gracefully

### SwiftShadow Integration
- Capture SwiftShadow logs through Python logging hierarchy
- Handle optional dependency gracefully
- Provide clear error messages when SwiftShadow is unavailable
- Test both QuickProxy and ProxyInterface code paths

### Backward Compatibility
- Maintain all existing CLI flags
- Preserve existing output formats
- Keep existing configuration file support
- Ensure existing tests continue to pass

### Performance Considerations
- Minimize overhead of dynamic display updates
- Efficient proxy tracking data structures
- Lazy loading of Rich components
- Optimize logging performance for high-volume operations

This design provides a comprehensive solution to the identified issues while maintaining the existing functionality and improving the overall user experience.