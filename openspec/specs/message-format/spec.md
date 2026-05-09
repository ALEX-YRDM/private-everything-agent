## MODIFIED Requirements

### Requirement: WebSocket message format supports attachments
The system SHALL extend the WebSocket message protocol to support file attachments alongside existing text and image attachments.

#### Scenario: Message with text and files
- **WHEN** client sends a message with user text and file attachments
- **THEN** message payload includes:
  - `type: "message"`
  - `content: "..."` (user text)
  - `images: [...]` (optional, existing image attachments)
  - `files: [{name, mime_type, content}, ...]` (new file attachments)

#### Scenario: Message with files and images
- **WHEN** client sends a message with both image and file attachments
- **THEN** message payload contains both:
  - `images: [...]` (base64 image data URLs)
  - `files: [{name, mime_type, content}, ...]` (base64 file data)
- **AND** both are processed and sent to the AI model

#### Scenario: File attachment structure
- **WHEN** files are included in message payload
- **THEN** each file attachment contains:
  - `name`: original filename with extension
  - `mime_type`: MIME type of the file
  - `content`: base64-encoded file content
- **AND** server validates file size before processing (max 10MB)

#### Scenario: Backward compatibility
- **WHEN** legacy clients send messages without `files` field
- **THEN** server processes them normally
- **AND** `files` field is optional and defaults to empty array
