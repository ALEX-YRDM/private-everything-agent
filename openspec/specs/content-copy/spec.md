## ADDED Requirements

### Requirement: User can copy message content to clipboard
The system SHALL provide copy buttons that allow users to copy message content to their clipboard.

#### Scenario: Copy user input text
- **WHEN** user hovers over their own message
- **THEN** a copy button appears
- **AND** clicking the button copies the message text to clipboard
- **AND** a "Copied" toast notification appears

#### Scenario: Copy AI response text
- **WHEN** user hovers over an AI response message
- **THEN** a copy button appears
- **AND** clicking the button copies the response text to clipboard
- **AND** a "Copied" toast notification appears

#### Scenario: Copy code block
- **WHEN** user hovers over a code block in the response
- **THEN** a copy button appears over the code block
- **AND** clicking copies only the code content (without markdown fence markers)
- **AND** a "Copied" toast notification appears

#### Scenario: Copy tool output
- **WHEN** user hovers over a tool call result block
- **THEN** a copy button appears
- **AND** clicking copies the tool output text to clipboard
- **AND** a "Copied" toast notification appears

### Requirement: Copy operation supports rich text format
The system SHALL copy content in both HTML and plain text formats for compatibility with various paste destinations (rich text editors, emails, word processors, etc.).

#### Scenario: Copy with HTML formatting
- **WHEN** user copies formatted content (e.g., code block, markdown-rendered text)
- **THEN** the clipboard contains both HTML (with formatting) and plain text versions
- **AND** when pasted into rich text applications, formatting is preserved
- **AND** when pasted into plain text applications, plain text version is used

#### Scenario: Copy plain content
- **WHEN** user copies simple text content
- **THEN** clipboard contains plain text
- **AND** HTML format is also available for compatibility

### Requirement: Copy operation provides user feedback
The system SHALL indicate successful copy operations to the user.

#### Scenario: Success notification
- **WHEN** content is successfully copied
- **THEN** a toast notification appears with message "Copied to clipboard" or equivalent
- **AND** the notification auto-dismisses after 2-3 seconds

#### Scenario: Copy failure handling
- **WHEN** clipboard access is denied (browser permission/security issue)
- **THEN** an error notification appears explaining the issue
- **AND** user is informed clipboard access is not available
