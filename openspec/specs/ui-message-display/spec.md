## MODIFIED Requirements

### Requirement: User messages display file attachments
The system SHALL display information about uploaded file attachments in user message bubbles.

#### Scenario: Show file list in message
- **WHEN** user message contains file attachments
- **THEN** the message bubble displays:
  - File icon (📎 or similar)
  - Original filename
  - File size in human-readable format
- **AND** file information appears below or alongside the user text

#### Scenario: Multiple files display
- **WHEN** message has multiple files
- **THEN** all files are listed with their names and sizes
- **AND** files are grouped together in a files section

#### Scenario: Files and images together
- **WHEN** message has both image and file attachments
- **THEN** images section displays as before
- **AND** files section displays below or separately
- **AND** both are clearly distinguished

### Requirement: Content blocks display copy buttons
The system SHALL provide copy-to-clipboard buttons for various content blocks in messages.

#### Scenario: Copy button appears on hover
- **WHEN** user hovers over a message content block (text, code, tool output)
- **THEN** a copy button (icon or button) appears
- **AND** button is visually distinct and easy to locate
- **AND** button remains visible while hovering over content area

#### Scenario: Copy code block specifically
- **WHEN** a code block is displayed in the response
- **THEN** a copy button appears in the code block header or corner
- **AND** copy includes only code content (no markdown fence)
- **AND** copy operation handles syntax highlighting gracefully

#### Scenario: Copy button on all content types
- **WHEN** user hovers over any copyable content (user message, AI response, tool output, code block)
- **THEN** an appropriate copy button appears
- **AND** all copy operations follow the same UX pattern (button style, feedback notification)

#### Scenario: Visual feedback on copy
- **WHEN** user clicks copy button
- **THEN** a toast notification appears: "Copied to clipboard"
- **AND** notification auto-dismisses after 2-3 seconds
- **AND** copy button may show temporary "Copied!" state before reverting
