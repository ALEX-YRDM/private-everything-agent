# Implementation Tasks: File Upload and Copy to Clipboard

## 1. Backend Dependencies Setup

- [x] 1.1 Add `python-docx` to `pyproject.toml`
- [x] 1.2 Add `openpyxl` to `pyproject.toml`
- [x] 1.3 Add `chardet` to `pyproject.toml` (for encoding detection)
- [x] 1.4 Run `pip install -e .` to install dependencies locally

## 2. Database Schema Migration

- [x] 2.1 Create database migration script to add `files` column to `messages` table
- [x] 2.2 Set `files` column type to JSON with default NULL
- [x] 2.3 Verify migration is backward compatible (old messages have null files)

## 3. Backend File Parsing Module

- [x] 3.1 Create `backend/tools/file_parser.py` module
- [x] 3.2 Implement `detect_file_type(filename: str) -> str` function (returns MIME type)
- [x] 3.3 Implement `parse_plain_text(content: bytes, filename: str) -> str` (use chardet for encoding)
- [x] 3.4 Implement `parse_code_file(content: bytes, filename: str) -> str` (direct UTF-8 read)
- [x] 3.5 Implement `parse_docx(content: bytes, filename: str) -> str` using python-docx
- [x] 3.6 Implement `parse_xlsx(content: bytes, filename: str) -> str` using openpyxl (extract all sheets)
- [x] 3.7 Implement `parse_file(name: str, mime_type: str, content: bytes) -> str` dispatcher
- [x] 3.8 Add comprehensive error handling (return error message string on parse failure)
- [x] 3.9 Add file type validation (reject unsupported extensions, max 10MB check)
- [ ] 3.10 Add unit tests for each file type parser

## 4. Backend WebSocket Extension

- [x] 4.1 Update `backend/api/websocket.py` to handle `files` field in message payload
- [x] 4.2 Decode base64 file content from WebSocket message
- [x] 4.3 Validate file sizes and types before processing
- [x] 4.4 Call file parser for each file (handle parse errors)
- [x] 4.5 Update error handling to return parse errors to frontend via WebSocket

## 5. Backend Agent Loop Integration

- [x] 5.1 Update `AgentLoop.process_stream()` signature to accept `files` parameter
- [x] 5.2 Prepare file content for AI context (format as "[File: {name}]\n{parsed_content}" or similar)
- [x] 5.3 Include file content in AI prompt/context
- [x] 5.4 Test that AI receives and can reference file content

## 6. Backend Message Storage

- [x] 6.1 Update message database schema to include `files` field
- [x] 6.2 Update `save_turn()` in session manager to persist file metadata
- [x] 6.3 Store `files` as JSON: `[{"name": "...", "mime_type": "...", "parsed_content": "..."}, ...]`
- [x] 6.4 Verify message retrieval includes files data
- [x] 6.5 Update API response types to include files in message schema

## 7. Frontend Type Definitions

- [x] 7.1 Update `DisplayMessage` interface in `stores/chat.ts` to include `files` array
- [x] 7.2 Define `FileAttachment` type: `{ name: string; mime_type: string; parsed_content?: string }`
- [x] 7.3 Update WebSocket message type to include optional `files` field
- [x] 7.4 Update API types in `api/http.ts` to match backend

## 8. Frontend File Input UI (ChatPanel.vue)

- [x] 8.1 Add file input hidden element `<input type="file" ref="fileInputRef" multiple>`
- [x] 8.2 Create file attachment display section (show uploaded file names before sending)
- [x] 8.3 Implement `onClickUploadFile()` to trigger file picker
- [x] 8.4 Implement `onFileInputChange()` to read selected files
- [x] 8.5 Implement `addFiles(files: FileList)` to validate and store files
- [x] 8.6 Implement `removeFile(index: number)` to remove file from attachment list
- [x] 8.7 Add file size validation (reject > 10MB with warning toast)
- [x] 8.8 Add file type validation (check extension against supported list)
- [x] 8.9 Add drag-and-drop handlers: `@drop="handleDrop"`, `@dragover="handleDragOver"`
- [x] 8.10 Implement `handleDrop()` to accept dropped files
- [x] 8.11 Clear file attachments after sending message
- [x] 8.12 Ensure files are only sent if vision/file support is enabled

## 9. Frontend WebSocket File Transmission

- [x] 9.1 Update `sendMessage()` to read files as base64
- [x] 9.2 Update WebSocket message construction to include `files` field
- [x] 9.3 Handle large file encoding (base64 conversion, progress feedback if needed)
- [x] 9.4 Send message with structure: `{type: "message", content, images, files}`
- [x] 9.5 Test WebSocket transmission with actual file uploads

## 10. Frontend Message Display (MessageBubble.vue)

- [x] 10.1 Add file section to user message template
- [x] 10.2 Render file list with icon, name, and size
- [x] 10.3 Format file size in human-readable format (B, KB, MB)
- [x] 10.4 Style file attachment section
- [x] 10.5 Test file display with sample messages

## 11. Frontend Copy Button: User Messages

- [x] 11.1 Add copy button to user message content section
- [x] 11.2 Implement copy button trigger on hover
- [x] 11.3 Implement `copyUserMessage()` function
- [x] 11.4 Use `navigator.clipboard.write()` for HTML + plain text format
- [x] 11.5 Show toast "Copied to clipboard" on success
- [x] 11.6 Handle clipboard permission errors with error toast
- [x] 11.7 Test on multiple browsers (Chrome, Firefox, Safari)

## 12. Frontend Copy Button: AI Response Text

- [x] 12.1 Add copy button to AI response content section
- [x] 12.2 Implement copy button trigger on hover
- [x] 12.3 Implement `copyAssistantMessage()` function
- [x] 12.4 Copy markdown-rendered content as HTML + plain text
- [x] 12.5 Show toast "Copied to clipboard" on success
- [x] 12.6 Test with various markdown content (lists, bold, links, etc.)

## 13. Frontend Copy Button: Code Blocks

- [x] 13.1 Identify where code blocks are rendered (markdown parsing output)
- [x] 13.2 Add copy button to code block header/corner
- [x] 13.3 Extract code content (without markdown fence markers)
- [x] 13.4 Implement `copyCodeBlock()` function
- [x] 13.5 Copy as plain text + HTML with syntax highlighting preserved
- [x] 13.6 Show toast "Copied to clipboard" on success
- [x] 13.7 Test with multiple language code blocks

## 14. Frontend Copy Button: Tool Outputs

- [x] 14.1 Locate tool call output display in ToolCallCard.vue
- [x] 14.2 Add copy button to tool result section
- [x] 14.3 Implement `copyToolResult()` function
- [x] 14.4 Show toast on success
- [x] 14.5 Test with various tool outputs

## 15. Frontend Copy: Mobile Fallback

- [x] 15.1 Detect mobile browser (touch-capable)
- [ ] 15.2 Implement long-press gesture for copy on mobile
- [x] 15.3 Show explicit copy button on mobile (always visible, not hover-only)
- [x] 15.4 Add clipboard polyfill if needed (for browser compatibility)
- [ ] 15.5 Test on iOS Safari and Android Chrome

## 16. Frontend Store Updates (chat.ts)

- [x] 16.1 Update `convertMessages()` to handle `files` field from API
- [x] 16.2 Update `handleStreamEvent()` to include file data if provided
- [x] 16.3 Update `sendMessage()` to include files in WebSocket transmission
- [x] 16.4 Verify streaming messages properly handle file data

## 17. Frontend UI Polish

- [x] 17.1 Style file attachment section to match image attachment style
- [x] 17.2 Add visual hover state to copy buttons
- [x] 17.3 Add visual feedback when copy is successful (button state change)
- [x] 17.4 Ensure responsive layout on mobile/tablet
- [x] 17.5 Add appropriate icons (📎 for files, 📋 for copy)

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
- [x] 19.3 Add comments to file_parser.py explaining each parser
- [ ] 19.4 Update API documentation (WebSocket message format)
- [x] 19.5 Remove any debug logging
- [x] 19.6 Run linter/formatter on all changed files

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
