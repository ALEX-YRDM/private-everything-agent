## MODIFIED Requirements

### Requirement: Messages store file attachment metadata
The system SHALL persist file attachment information and parsed content in the message history for future retrieval and display.

#### Scenario: Store file metadata and content
- **WHEN** a message with file attachments is received and processed
- **THEN** the message database record includes:
  - `files` JSON field containing array of file objects
  - Each file object contains: `name`, `mime_type`, `parsed_content`
  - Parsed content is the extracted text from the file

#### Scenario: Retrieve message with files
- **WHEN** user opens a previous conversation with file attachments
- **THEN** the API returns complete file metadata
- **AND** file information is displayed in the UI
- **AND** original parsed content is available to the AI if the message is referenced

#### Scenario: File content included in AI context
- **WHEN** a message with parsed file content is used in subsequent AI interactions
- **THEN** the parsed file content remains available in the message history
- **AND** the AI can reference or analyze the file content if needed

#### Scenario: Messages without files
- **WHEN** a message has no file attachments
- **THEN** the `files` field is empty array or null
- **AND** message processing works as before (backward compatible)
