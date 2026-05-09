# Design: File Upload and Copy to Clipboard

## Context

The current chat system supports text input and image uploads. Users frequently need to share documents (Word, Excel, code) with the AI for analysis. Additionally, users often want to copy content (their input, AI responses, code blocks) to use elsewhere.

### Current State
- **Frontend**: ChatPanel.vue handles image uploads via file picker and drag-drop
- **Backend**: Agent loop receives `user_content` (string) and `images` (list of base64 data URLs)
- **WebSocket**: Message format: `{type: "message", content: "...", images: [...]}`
- **Database**: Messages stored with `content` and tool-related fields; no file support
- **UI**: MessageBubble.vue displays text and images; no copy buttons exist

### Constraints
- File size limit: 10MB (consistent with images)
- Supported formats: plaintext, code files, Word (.docx), Excel (.xlsx)
- PDF not supported in v1
- WebSocket-based file transmission (not separate HTTP upload)
- Parse errors should be reported to user immediately

## Goals / Non-Goals

**Goals:**
- Users can select/drag-drop files (multiple, up to 10MB each) into chat input
- Backend parses files and extracts text content using appropriate Python libraries
- Parsed content sent to AI model with user message
- File metadata and content persisted in message history
- UI displays file attachments in message bubbles
- Copy-to-clipboard buttons on all text content (user input, AI output, code blocks)
- Copy operations support both HTML and plain text formats
- User receives feedback (toast) when content is copied

**Non-Goals:**
- PDF support (v1)
- Async/background file parsing (inline only)
- File preview or rendering in chat UI
- Upload progress indicators
- Virus scanning or security analysis
- File deletion or editing after upload

## Decisions

### 1. File Transmission via WebSocket (not separate HTTP API)
**Decision**: Files transmitted as base64 in WebSocket messages, not uploaded separately via HTTP.

**Rationale**: 
- Simpler architecture (single communication channel)
- Reuses existing WebSocket auth and session context
- Consistent with current image upload pattern
- Acceptable latency for typical use (most users won't upload 10MB files frequently)

**Alternatives Considered**:
- Separate REST API for file upload → adds complexity, separate auth, progress tracking overhead
- HTTP streaming → overkill for single-user chat, complicates WebSocket message flow

**Trade-off**: Large file transfers (10MB) will be slower than optimized HTTP, but acceptable for chat use case.

---

### 2. Backend File Parsing (not frontend)
**Decision**: File parsing happens on backend using Python libraries.

**Rationale**:
- Rich Python ecosystem (docx, openpyxl, chardet)
- JS libraries have limited .docx/.xlsx support
- Consistent parsing across all clients
- Easier to maintain and update

**Alternatives Considered**:
- Frontend-only parsing with JS libraries → limited format support, no PDF future-proofing
- Hybrid (frontend for simple, backend for complex) → unnecessary complexity

**Trade-off**: Slightly more server CPU usage, but acceptable given single-user architecture.

---

### 3. WebSocket Message Format Extension (new `files` field)
**Decision**: Add optional `files` array to message payload alongside `images`.

```json
{
  "type": "message",
  "content": "user text",
  "images": ["data:image/..."],
  "files": [
    {
      "name": "report.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "content": "base64-encoded file..."
    }
  ]
}
```

**Rationale**:
- Separates concerns (images vs. files)
- Extensible for future file metadata (page count, dimensions, etc.)
- Clear semantics for backend processing
- Easy to version/deprecate if needed

**Alternatives Considered**:
- Merge files into `content` string → loses structure, harder to extract and re-use
- Use separate `file_id` references → requires two-step process, more complex

**Trade-off**: Slightly larger WebSocket messages, but negligible impact.

---

### 4. File Content Stored in Database (not as separate attachments)
**Decision**: Parsed file content stored as JSON in `messages.files` field.

```sql
ALTER TABLE messages ADD COLUMN files JSON DEFAULT NULL;
-- files: [
--   {"name": "...", "mime_type": "...", "parsed_content": "..."},
--   ...
-- ]
```

**Rationale**:
- Simple schema change (single JSON column)
- Keeps message and context together (important for AI history)
- No separate file storage infrastructure needed
- Files deleted when message is deleted (clean lifecycle)

**Alternatives Considered**:
- Separate `files` table with FK to messages → overkill, adds join complexity
- External file storage (S3) → unnecessary for single-user system
- Compress file content → not needed for typical usage

**Trade-off**: Database message records larger, but acceptable (typical parsed file < 500KB).

---

### 5. Display File Attachments as Metadata (not full content)
**Decision**: Show filename + size in UI; don't display full parsed content inline.

```
User message:
  "I need help with this report"
  📎 report.docx (450 KB)
  📎 data.csv (12 KB)
```

**Rationale**:
- Keeps UI clean and readable
- Large parsed content (10MB file → millions of chars) would clutter UI
- AI receives full content, doesn't need to be visible to user
- User can request "show me what you parsed from the file" if needed

**Alternatives Considered**:
- Show full parsed content inline → clutters UI, hard to read
- Show preview/excerpt → requires UI logic to truncate, inconsistent

**Trade-off**: User doesn't see exactly what AI received, but this is acceptable (AI can be asked to quote relevant parts).

---

### 6. Copy Button UX: Hover-Triggered, Toast Feedback
**Decision**: Copy button appears on hover; click copies and shows toast "Copied to clipboard".

**Rationale**:
- Hover reveals buttons only when user indicates intent
- Toast provides clear, non-intrusive feedback
- Consistent with common web patterns (GitHub, Slack, etc.)
- No need for permanent UI clutter with copy buttons

**Alternatives Considered**:
- Always-visible copy button → clutters UI, especially for long messages
- Right-click context menu → less discoverable
- No feedback → user uncertain if copy succeeded

**Trade-off**: Mobile users may not have hover; implement fallback (long-press or explicit button for mobile).

---

### 7. Copy Format: HTML + Plain Text via Clipboard API
**Decision**: Use `navigator.clipboard.write()` with both `text/html` and `text/plain` MIME types.

```javascript
const htmlContent = "<p>formatted content</p>";
const plainText = "formatted content";
await navigator.clipboard.write([
  new ClipboardItem({
    "text/html": new Blob([htmlContent], { type: "text/html" }),
    "text/plain": new Blob([plainText], { type: "text/plain" }),
  })
]);
```

**Rationale**:
- HTML format preserves syntax highlighting when pasted into rich editors
- Plain text fallback for simple text apps
- Browser handles format negotiation automatically
- No library dependency needed

**Alternatives Considered**:
- Plain text only → lose formatting when pasted into Word/email
- HTML only → break on paste into simple text editors
- Custom format → not portable

**Trade-off**: Slightly more complex code, but better UX for users pasting into various contexts.

---

### 8. Code Block Copy: Extract Code Only (no fence markers)
**Decision**: Copy button on code blocks copies only the code, not the markdown fence (```language...```).

**Rationale**:
- User usually wants to paste executable code, not markdown
- Reduces friction when copying to editor/REPL
- Markdown fence is metadata, not content user typically wants

**Alternatives Considered**:
- Copy with fence markers → user has to delete them
- Copy as HTML with highlighting → less portable, breaks in many editors

**Trade-off**: User can't copy the raw markdown by default, but can select-all and copy if needed.

---

## Risks / Trade-offs

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Large file slow to transmit (10MB base64) | Medium | Accept as limitation; document typical upload time (~5-10s on 4G). Feature primarily for < 5MB files. |
| Base64 expands file size by ~33% | Low | Unavoidable with current architecture; acceptable for typical use. |
| Malformed file crashes parser | Medium | Wrap file parsing in try-catch; return user-friendly error message. Test with sample corrupted files. |
| Excel with huge number of rows → massive parsed content | Medium | Consider optional size limit on parsed output (truncate if > 2MB). Warn user if parse is incomplete. |
| Mobile browser doesn't support Clipboard API | Low | Provide fallback: copy button shows toast and opens text selection dialog. Use `clipboard` library for polyfill if needed. |
| Database message size grows significantly | Low | No mitigation needed; typical message < 1MB. Monitor DB growth, consider archival in future. |
| Missing file type → silent failure | Medium | Validate extension on frontend before sending; provide clear error if unsupported type. |

## Architecture Diagram

```
┌──────────────────────────────────────┐
│         Frontend (Vue)                │
├──────────────────────────────────────┤
│ ChatPanel.vue:                       │
│  • File picker + drag-drop input     │
│  • Read file → base64                │
│  • Show file list in input           │
│                                      │
│ MessageBubble.vue:                   │
│  • Display file metadata             │
│  • Copy buttons (hover)              │
│  • Toast notifications               │
└───────────────┬──────────────────────┘
                │ WebSocket
                │ {type: "message",
                │  content: "...",
                │  files: [{name, mime, content}, ...],
                │  images: [...]}
                │
┌───────────────▼──────────────────────┐
│       Backend (FastAPI)               │
├──────────────────────────────────────┤
│ WebSocket Handler (websocket.py):    │
│  • Receive message + files           │
│  • Validate file sizes & types       │
│  • Dispatch to FileParser            │
│                                      │
│ FileParser (new module):             │
│  • Detect file type by extension     │
│  • Route to appropriate handler:     │
│    - Plain text: direct read         │
│    - Code: read with chardet         │
│    - DOCX: python-docx extract       │
│    - XLSX: openpyxl extract          │
│  • Return parsed content             │
│                                      │
│ AgentLoop.process_stream():          │
│  • Receive parsed files              │
│  • Include in AI context             │
│                                      │
│ Database (save_turn):                │
│  • Store messages.files JSON         │
│  • Include metadata + content        │
└──────────────────────────────────────┘
```

## Migration Plan

### Phase 1: Database Schema Update
- Add `files` JSON column to `messages` table
- Migration is additive (backward compatible)

### Phase 2: Backend Implementation
1. Create `file_parser.py` module with parsing logic
2. Update `AgentLoop.process_stream()` to accept `files` parameter
3. Update message storage to persist files
4. Add file parsing error handling

### Phase 3: Frontend Implementation
1. Update ChatPanel to handle file input (picker + drag-drop)
2. Update store type definitions for `DisplayMessage.files`
3. Update MessageBubble to display file metadata
4. Add copy buttons and clipboard logic

### Rollout
- No breaking changes for existing functionality
- Old clients (without file support) continue to work
- New clients automatically benefit from file support

## Open Questions

1. **Error Handling for Partial Parse**: If Excel has 1M rows but we truncate to 2MB content, should we show a warning? → **Decision needed**: Yes, warn user content is truncated.
2. **File Encoding Detection**: Fallback encoding if chardet fails? → **Decision**: UTF-8 default.
3. **XLSX Preserving Format**: How much formatting detail to preserve (colors, fonts)? → **Decision**: Preserve structure only (no styling).
4. **Copy Button Mobile**: Use long-press or always-visible on mobile? → **Decision**: Long-press + fallback button visible on mobile.
5. **Future: Rename "Files" Button**: Currently "📎" icon. Better name? → **Decision**: Keep "📎" + "Files" label for clarity.
