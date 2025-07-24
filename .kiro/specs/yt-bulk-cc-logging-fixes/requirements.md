# Requirements Document

## Introduction

This feature addresses critical issues in the YouTube Bulk CC downloader related to logging, console output, proxy management, and user experience. The tool currently has problems with duplicate log entries, missing emojis in output, unclear proxy usage feedback, and poor dynamic status display. This enhancement will fix these issues while maintaining all existing functionality and ensuring comprehensive test coverage.

## Requirements

### Requirement 1

**User Story:** As a user running yt-bulk-cc, I want clear separation between console output and log file content, so that I don't see duplicate information and can understand what's happening in real-time.

#### Acceptance Criteria

1. WHEN the tool runs THEN the final summary SHALL appear in both console and log file as separate, independent entries
2. WHEN content is printed to console THEN it SHALL NOT automatically appear at the beginning of the log file
3. WHEN logging to file THEN debug-level information SHALL always be captured regardless of console verbosity
4. WHEN using -v or -vv flags THEN console verbosity SHALL be controlled independently from log file verbosity
5. WHEN the final summary is generated THEN it SHALL be logged separately from console printing to avoid duplication in log files

### Requirement 2

**User Story:** As a user, I want to see emojis and clear status indicators in the output, so that I can quickly understand the results and current state.

#### Acceptance Criteria

1. WHEN displaying summary statistics THEN the system SHALL use emojis (✓, ↯, ⚠, 🚫) instead of plain text (ok=, banned=)
2. WHEN showing proxy status THEN the system SHALL use appropriate emoji indicators
3. WHEN displaying file statistics THEN the system SHALL include emoji prefixes for visual clarity
4. WHEN showing videos without captions THEN each entry SHALL be prefixed with appropriate emoji

### Requirement 3

**User Story:** As a user utilizing proxies, I want clear visibility into proxy usage, rotation, and status, so that I can understand network behavior and troubleshoot issues.

#### Acceptance Criteria

1. WHEN public proxies are loaded THEN the system SHALL log the source and count of loaded proxies
2. WHEN a proxy is used for a request THEN the system SHALL log which proxy is being used
3. WHEN a proxy fails or gets banned THEN the system SHALL log the specific proxy and reason
4. WHEN proxies are rotated THEN the system SHALL indicate the rotation in logs
5. WHEN SwiftShadow is used THEN all SwiftShadow logs SHALL be captured and included in the main log

### Requirement 4

**User Story:** As a user, I want a dynamic status display that updates in place, so that I can see current progress without screen clutter.

#### Acceptance Criteria

1. WHEN the tool is running THEN there SHALL be a dynamic status section that updates in place using Rich or equivalent
2. WHEN processing videos THEN the status SHALL show current task without reprinting (e.g., "Status: doing XYZ...")
3. WHEN using proxies THEN the dynamic display SHALL show list of proxies in use with their identifiers
4. WHEN downloading transcripts THEN the display SHALL show current count of completed downloads
5. WHEN the dynamic section updates THEN it SHALL NOT create new lines or scroll the screen
6. WHEN no proxies are being used THEN the proxy section SHALL NOT be displayed
7. WHEN concurrent jobs are running THEN the display SHALL show "Concurrent Jobs: N"

### Requirement 5

**User Story:** As a user with custom proxies, I want --proxy and --proxy-file options to work correctly, so that I can use my own proxy infrastructure.

#### Acceptance Criteria

1. WHEN using --proxy flag THEN custom user proxies SHALL be processed correctly
2. WHEN using --proxy-file flag THEN proxies from file SHALL be loaded and used
3. WHEN custom proxies are provided THEN they SHALL NOT be deprecated or removed
4. WHEN both custom and public proxies are used THEN custom proxies SHALL take precedence
5. WHEN testing proxy functionality THEN comprehensive tests SHALL verify both --proxy and --proxy-file work correctly

### Requirement 6

**User Story:** As a user, I want comprehensive final output with proper formatting and limits, so that I can review results effectively.

#### Acceptance Criteria

1. WHEN displaying file statistics THEN the system SHALL respect --summary-stats-top limit (renamed from --stats-top)
2. WHEN showing videos without captions THEN the list SHALL be limited by --summary-max-no-captions parameter
3. WHEN displaying failed downloads THEN the list SHALL be limited by --summary-max-failed parameter
4. WHEN showing proxy usage THEN the list SHALL be limited by --summary-max-proxies parameter
5. WHEN all sections are displayed THEN they SHALL only appear if there is relevant data to show

### Requirement 7

**User Story:** As a developer running tests, I want all existing functionality to continue working, so that no regressions are introduced.

#### Acceptance Criteria

1. WHEN running the test suite THEN all existing tests SHALL pass
2. WHEN using any existing CLI flags THEN they SHALL work exactly as before
3. WHEN processing videos, playlists, or channels THEN core functionality SHALL remain unchanged
4. WHEN using different output formats THEN all formats SHALL work correctly
5. WHEN concatenating files THEN the concatenation logic SHALL work as expected

### Requirement 8

**User Story:** As a user, I want proper error handling and console output, so that I don't see confusing error messages or exceptions.

#### Acceptance Criteria

1. WHEN network errors occur THEN they SHALL be handled gracefully without showing stack traces to users
2. WHEN proxy validation fails THEN the system SHALL continue with available proxies
3. WHEN cache operations fail THEN appropriate fallback behavior SHALL be implemented
4. WHEN file operations encounter errors THEN clear error messages SHALL be displayed
5. WHEN the tool exits THEN cleanup SHALL occur properly without showing cleanup errors to users
6. WHEN console errors appear THEN they SHALL be investigated and resolved to provide clean user experience

### Requirement 9

**User Story:** As a developer, I want comprehensive test coverage that validates real functionality, so that all features work correctly without being artificially fitted to tests.

#### Acceptance Criteria

1. WHEN running the complete test suite THEN all tests SHALL pass without modification
2. WHEN tests are written THEN they SHALL test real functionality rather than being fitted to existing code
3. WHEN proxy functionality is tested THEN both --proxy and --proxy-file options SHALL have comprehensive test coverage
4. WHEN custom proxy tests run THEN they SHALL verify that custom proxies work independently of public proxy functionality
5. WHEN all features are tested THEN the test suite SHALL validate actual user scenarios rather than implementation details