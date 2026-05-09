## Why

Currently, users can only provide input via text and images. Many users need to share structured documents (Word, Excel, code files, Markdown) with the AI for analysis and processing. Additionally, the UI lacks the ability for users to copy content (their own input, AI responses, and code blocks) to clipboard for reuse elsewhere. These are common features that significantly improve usability.

## What Changes

### File Upload & Parsing
- Users can upload documents (`.docx`, `.xlsx`, `.txt`, `.md`, `.json`, `.csv`, code files) via file picker or drag-drop
- File size limited to 10MB per file (consistent with image limit)
- Backend parses file content based on type:
  - Plain text files (`.txt`, `.md`, `.json`, etc.): direct file reading
  - Code files (`.py`, `.js`, `.ts`, etc.): direct file reading
  - `.docx` files: text extraction via `python-docx`
  - `.xlsx` files: content extraction per sheet via `openpyxl`
- Parsed content sent to AI model along with user message
- File metadata and parsed content stored in database for message history
- Parse errors return error message to user directly

### Copy to Clipboard
- User input content: copy button to copy text to clipboard
- AI response content: copy button to copy rendered content
- Code blocks in responses: copy button to copy code only (without markdown fence)
- Tool call outputs: copy button to copy content
- All copy operations support HTML + plain text formats for rich paste experience
- Success feedback via Toast notification

### UI Enhancements
- File attachment section in chat input (similar to image attachment display)
- Copy buttons appear on hover over content blocks
- File list displayed in user messages showing filename and size

## Capabilities

### New Capabilities
- `file-upload`: Support uploading and parsing various document formats (.docx, .xlsx, .txt, .md, .json, .csv, code files)
- `content-copy`: Enable users to copy text content to clipboard from chat messages and code blocks

### Modified Capabilities
- `message-format`: WebSocket message protocol extended to support file attachments
- `chat-message-storage`: Database message storage extended to include file metadata and parsed content
- `ui-message-display`: Chat message UI enhanced to display file attachments and copy buttons

## Impact

### Backend
- New dependencies: `python-docx`, `openpyxl`, `chardet` (encoding detection)
- WebSocket message schema extended: new `files` field in message payload
- New file parsing logic in agent loop
- Database schema: `messages` table needs `files` field (JSON)

### Frontend
- ChatPanel: new file upload UI component and drag-drop handling
- MessageBubble: new file display section and copy buttons for content
- Store: extended message type to include `files` array
- API types: updated to support file attachment in WebSocket protocol

### Breaking Changes
- WebSocket message format changed: clients expecting old format need update
