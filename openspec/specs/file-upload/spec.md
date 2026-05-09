## ADDED Requirements

### Requirement: User can select and upload files
The system SHALL allow users to select files from their file system via a file picker dialog or drag-and-drop interface, with file size limited to 10MB per file.

#### Scenario: File picker upload
- **WHEN** user clicks the file upload button
- **THEN** a native file picker dialog appears
- **AND** user can select one or more files
- **AND** only files under 10MB are accepted

#### Scenario: Drag-and-drop upload
- **WHEN** user drags files over the chat input area
- **THEN** a visual drop zone indicator appears
- **AND** dropping files adds them to the attachment list
- **AND** only files under 10MB are accepted

#### Scenario: File size validation
- **WHEN** user selects a file larger than 10MB
- **THEN** a warning message displays: "File {name} exceeds 10MB limit"
- **AND** the file is not added to the attachment list

### Requirement: System parses uploaded files
The system SHALL extract text content from uploaded files based on their type and make the content available to the AI model.

#### Scenario: Plain text file parsing
- **WHEN** user uploads a `.txt`, `.md`, `.json`, `.csv`, or `.yaml` file
- **THEN** the file is read as plain text (with automatic encoding detection)
- **AND** the complete file content is extracted

#### Scenario: Code file parsing
- **WHEN** user uploads a code file (`.py`, `.js`, `.ts`, `.java`, `.cpp`, `.go`, `.rb`, `.php`, `.c`, `.h`, etc.)
- **THEN** the file is read as plain text
- **AND** the complete file content is extracted

#### Scenario: Word document parsing
- **WHEN** user uploads a `.docx` file
- **THEN** text content is extracted from all paragraphs
- **AND** basic formatting structure (headings, lists) is preserved as text
- **AND** extracted content is sent to the AI model

#### Scenario: Excel spreadsheet parsing
- **WHEN** user uploads a `.xlsx` file
- **THEN** content from all sheets is extracted
- **AND** each sheet's data is presented as a text table or structured format
- **AND** sheet names and cell structure are preserved for readability

#### Scenario: Unsupported file type
- **WHEN** user selects a file with an unsupported extension (e.g., `.pdf`, `.zip`, `.exe`)
- **THEN** an error message displays: "File type {extension} is not supported"
- **AND** the file is not added

### Requirement: Parse errors are handled gracefully
The system SHALL return clear error messages when file parsing fails.

#### Scenario: Corrupted document
- **WHEN** a file fails to parse due to corruption or invalid format
- **THEN** an error message displays explaining the parsing failure
- **AND** the message is not sent to the AI model

#### Scenario: Encoding issues
- **WHEN** a text file cannot be decoded using detected encoding
- **THEN** an error message displays
- **AND** the file is not processed

### Requirement: File content is sent with user message
The system SHALL include parsed file content in the message sent to the AI model.

#### Scenario: Single file with text
- **WHEN** user sends a message with one attached file
- **THEN** the parsed file content is included in the message sent to the AI
- **AND** the file name and parsed content are both transmitted

#### Scenario: Multiple files
- **WHEN** user sends a message with multiple attached files
- **THEN** all parsed file contents are included in the message
- **AND** each file is identified by name and file type

#### Scenario: Files and images together
- **WHEN** user sends a message with both image attachments and file attachments
- **THEN** both are included in the message sent to the AI model
- **AND** they are transmitted with appropriate metadata
