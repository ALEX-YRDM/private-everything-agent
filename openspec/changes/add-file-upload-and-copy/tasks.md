# Implementation Tasks: File Upload and Copy to Clipboard

## 1. Backend Dependencies Setup

- [ ] 1.1 Add `python-docx` to `pyproject.toml`
- [ ] 1.2 Add `openpyxl` to `pyproject.toml`
- [ ] 1.3 Add `chardet` to `pyproject.toml` (for encoding detection)
- [ ] 1.4 Run `pip install -e .` to install dependencies locally

## 2. Database Schema Migration

- [ ] 2.1 Create database migration script to add `files` column to `messages` table
- [ ] 2.2 Set `files` column type to JSON with default NULL
- [ ] 2.3 Verify migration is backward compatible (old messages have null files)

## 3. Backend File Parsing Module

- [ ] 3.1 Create `backend/tools/file_parser.py` module
- [ ] 3.2 Implement `detect_file_type(filename: str) -> str` function (returns MIME type)
- [ ] 3.3 Implement `parse_plain_text(content: bytes, filename: str) -> str` (use chardet for encoding)
- [ ] 3.4 Implement `parse_code_file(content: bytes, filename: str) -> str` (direct UTF-8 read)
- [ ] 3.5 Implement `parse_docx(content: bytes, filename: str) -> str` using python-docx
- [ ] 3.6 Implement `parse_xlsx(content: bytes, filename: str) -> str` using openpyxl (extract all sheets)
- [ ] 3.7 Implement `parse_file(name: str, mime_type: str, content: bytes) -> str` dispatcher
- [ ] 3.8 Add comprehensive error handling (return error message string on parse failure)
- [ ] 3.9 Add file type validation (reject unsupported extensions, max 10MB check)
- [ ] 3.10 Add unit tests for each file type parser

## 4. Backend WebSocket Extension

- [ ] 4.1 Update `backend/api/websocket.py` to handle `files` field in message payload
- [ ] 4.2 Decode base64 file content from WebSocket message
- [ ] 4.3 Validate file sizes and types before processing
- [ ] 4.4 Call file parser for each file (handle parse errors)
- [ ] 4.5 Update error handling to return parse errors to frontend via WebSocket

## 5. Backend Agent Loop Integration

- [ ] 5.1 Update `AgentLoop.process_stream()` signature to accept `files` parameter
- [ ] 5.2 Prepare file content for AI context (format as "[File: {name}]\n{parsed_content}" or similar)
- [ ] 5.3 Include file content in AI prompt/context
- [ ] 5.4 Test that AI receives and can reference file content

## 6. Backend Message Storage

- [ ] 6.1 Update message database schema to include `files` field
- [ ] 6.2 Update `save_turn()` in session manager to persist file metadata
- [ ] 6.3 Store `files` as JSON: `[{"name": "...", "mime_type": "...", "parsed_content": "..."}, ...]`
- [ ] 6.4 Verify message retrieval includes files data
- [ ] 6.5 Update API response types to include files in message schema

## 7. Frontend Type Definitions

- [ ] 7.1 Update `DisplayMessage` interface in `stores/chat.ts` to include `files` array
- [ ] 7.2 Define `FileAttachment` type: `{ name: string; mime_type: string; parsed_content?: string }`
- [ ] 7.3 Update WebSocket message type to include optional `files` field
- [ ] 7.4 Update API types in `api/http.ts` to match backend

## 8. Frontend File Input UI (ChatPanel.vue)

- [ ] 8.1 Add file input hidden element `<input type="file" ref="fileInputRef" multiple>`
- [ ] 8.2 Create file attachment display section (show uploaded file names before sending)
- [ ] 8.3 Implement `onClickUploadFile()` to trigger file picker
- [ ] 8.4 Implement `onFileInputChange()` to read selected files
- [ ] 8.5 Implement `addFiles(files: FileList)` to validate and store files
- [ ] 8.6 Implement `removeFile(index: number)` to remove file from attachment list
- [ ] 8.7 Add file size validation (reject > 10MB with warning toast)
- [ ] 8.8 Add file type validation (check extension against supported list)
- [ ] 8.9 Add drag-and-drop handlers: `@drop="handleDrop"`, `@dragover="handleDragOver"`
- [ ] 8.10 Implement `handleDrop()` to accept dropped files
- [ ] 8.11 Clear file attachments after sending message
- [ ] 8.12 Ensure files are only sent if vision/file support is enabled

## 9. Frontend WebSocket File Transmission

- [ ] 9.1 Update `sendMessage()` to read files as base64
- [ ] 9.2 Update WebSocket message construction to include `files` field
- [ ] 9.3 Handle large file encoding (base64 conversion, progress feedback if needed)
- [ ] 9.4 Send message with structure: `{type: "message", content, images, files}`
- [ ] 9.5 Test WebSocket transmission with actual file uploads

## 10. Frontend Message Display (MessageBubble.vue)

- [ ] 10.1 Add file section to user message template
- [ ] 10.2 Render file list with icon, name, and size
- [ ] 10.3 Format file size in human-readable format (B, KB, MB)
- [ ] 10.4 Style file attachment section
- [ ] 10.5 Test file display with sample messages

## 11. Frontend Copy Button: User Messages

- [ ] 11.1 Add copy button to user message content section
- [ ] 11.2 Implement copy button trigger on hover
- [ ] 11.3 Implement `copyUserMessage()` function
- [ ] 11.4 Use `navigator.clipboard.write()` for HTML + plain text format
- [ ] 11.5 Show toast "Copied to clipboard" on success
- [ ] 11.6 Handle clipboard permission errors with error toast
- [ ] 11.7 Test on multiple browsers (Chrome, Firefox, Safari)

## 12. Frontend Copy Button: AI Response Text

- [ ] 12.1 Add copy button to AI response content section
- [ ] 12.2 Implement copy button trigger on hover
- [ ] 12.3 Implement `copyAssistantMessage()` function
- [ ] 12.4 Copy markdown-rendered content as HTML + plain text
- [ ] 12.5 Show toast "Copied to clipboard" on success
- [ ] 12.6 Test with various markdown content (lists, bold, links, etc.)

## 13. Frontend Copy Button: Code Blocks

- [ ] 13.1 Identify where code blocks are rendered (markdown parsing output)
- [ ] 13.2 Add copy button to code block header/corner
- [ ] 13.3 Extract code content (without markdown fence markers)
- [ ] 13.4 Implement `copyCodeBlock()` function
- [ ] 13.5 Copy as plain text + HTML with syntax highlighting preserved
- [ ] 13.6 Show toast "Copied to clipboard" on success
- [ ] 13.7 Test with multiple language code blocks

## 14. Frontend Copy Button: Tool Outputs

- [ ] 14.1 Locate tool call output display in ToolCallCard.vue
- [ ] 14.2 Add copy button to tool result section
- [ ] 14.3 Implement `copyToolResult()` function
- [ ] 14.4 Show toast on success
- [ ] 14.5 Test with various tool outputs

## 15. Frontend Copy: Mobile Fallback

- [ ] 15.1 Detect mobile browser (touch-capable)
- [ ] 15.2 Implement long-press gesture for copy on mobile
- [ ] 15.3 Show explicit copy button on mobile (always visible, not hover-only)
- [ ] 15.4 Add clipboard polyfill if needed (for browser compatibility)
- [ ] 15.5 Test on iOS Safari and Android Chrome

## 16. Frontend Store Updates (chat.ts)

- [ ] 16.1 Update `convertMessages()` to handle `files` field from API
- [ ] 16.2 Update `handleStreamEvent()` to include file data if provided
- [ ] 16.3 Update `sendMessage()` to include files in WebSocket transmission
- [ ] 16.4 Verify streaming messages properly handle file data

## 17. Frontend UI Polish

- [ ] 17.1 Style file attachment section to match image attachment style
- [ ] 17.2 Add visual hover state to copy buttons
- [ ] 17.3 Add visual feedback when copy is successful (button state change)
- [ ] 17.4 Ensure responsive layout on mobile/tablet
- [ ] 17.5 Add appropriate icons (📎 for files, 📋 for copy)

## 18. Integration Testing

- [ ] 18.1 End-to-end test: upload text file → backend parses → AI receives content
- [ ] 18.2 End-to-end test: upload .docx file → backend extracts text → verify in AI response
- [ ] 18.3 End-to-end test: upload .xlsx file → backend extracts all sheets → AI processes
- [ ] 18.4 End-to-end test: upload code file → backend reads correctly → AI analyzes
- [ ] 18.5 End-to-end test: upload multiple files → all processed and sent to AI
- [ ] 18.6 End-to-end test: upload large file (close to 10MB) → verify transmission
- [ ] 18.7 End-to-end test: upload unsupported file → error message displayed
- [ ] 18.8 End-to-end test: malformed file (corrupted docx/xlsx) → error message displayed
- [ ] 18.9 Test copy functionality: user message → verify clipboard content
- [ ] 18.10 Test copy functionality: AI response → verify clipboard content
- [ ] 18.11 Test copy functionality: code block → verify code only (no fence) in clipboard
- [ ] 18.12 Test message history: reload conversation → files still present and displayed

## 19. Documentation & Cleanup

- [ ] 19.1 Update README with file upload feature documentation
- [ ] 19.2 Document supported file formats and size limits
- [ ] 19.3 Add comments to file_parser.py explaining each parser
- [ ] 19.4 Update API documentation (WebSocket message format)
- [ ] 19.5 Remove any debug logging
- [ ] 19.6 Run linter/formatter on all changed files

## 20. Final Review & Testing

- [ ] 20.1 Run full test suite (backend + frontend unit tests)
- [ ] 20.2 Manual smoke test: basic chat still works without files
- [ ] 20.3 Manual smoke test: basic image upload still works
- [ ] 20.4 Manual smoke test: file upload with various formats
- [ ] 20.5 Manual smoke test: copy buttons work across content types
- [ ] 20.6 Performance test: large file parsing doesn't freeze UI
- [ ] 20.7 Browser compatibility check (Chrome, Firefox, Safari, Edge)
- [ ] 20.8 Mobile browser test (iOS Safari, Android Chrome)
- [ ] 20.9 Final code review (check for security issues)
- [ ] 20.10 Merge and close change
