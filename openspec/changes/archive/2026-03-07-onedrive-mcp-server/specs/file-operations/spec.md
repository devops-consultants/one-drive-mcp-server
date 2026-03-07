## ADDED Requirements

### Requirement: List files in a folder

The server SHALL provide a `list_files` tool that accepts a `path` parameter (default `"/"`) and returns an array of file/folder entries in that directory via the Microsoft Graph API.

Each entry SHALL include: `name`, `path`, `type` ("file" or "folder"), `size` (bytes, null for folders), `modified` (ISO 8601 timestamp), and `etag`.

#### Scenario: List root directory
- **WHEN** agent calls `list_files(path="/")`
- **THEN** server queries `GET /me/drive/root/children` and returns the entries

#### Scenario: List subfolder
- **WHEN** agent calls `list_files(path="/Documents/Reports")`
- **THEN** server queries `GET /me/drive/root:/Documents/Reports:/children` and returns the entries

#### Scenario: List non-existent folder
- **WHEN** agent calls `list_files(path="/nonexistent")`
- **THEN** server returns an error with `"error": "not_found"` and a descriptive message

#### Scenario: Permission denied on folder
- **WHEN** agent calls `list_files` on a folder the authenticated user cannot access
- **THEN** server returns an error with `"error": "permission_denied"` and a descriptive message

### Requirement: Read file content

The server SHALL provide a `read_file` tool that accepts a `path` parameter and returns the file content along with metadata.

The response SHALL include: `content` (UTF-8 string for text files, base64 string for binary), `etag`, `mime_type`, `size` (bytes), and `binary` (boolean).

Text files (mime_type starting with `text/`, `application/json`, `application/xml`, `application/yaml`, and similar) SHALL be returned as UTF-8 strings with `binary: false`. All other files SHALL be returned as base64-encoded strings with `binary: true`.

#### Scenario: Read a text file
- **WHEN** agent calls `read_file(path="/Documents/report.md")`
- **THEN** server queries `GET /me/drive/root:/Documents/report.md:/content` and returns the file content as UTF-8 with metadata

#### Scenario: Read a binary file
- **WHEN** agent calls `read_file(path="/Images/logo.png")`
- **THEN** server returns the file content as base64-encoded string with `binary: true`

#### Scenario: Read non-existent file
- **WHEN** agent calls `read_file` on a path that does not exist
- **THEN** server returns an error with `"error": "not_found"`

#### Scenario: Read file exceeding size limit
- **WHEN** agent calls `read_file` on a file larger than the configured maximum (default 25MB)
- **THEN** server returns an error with `"error": "file_too_large"` and the file size in the message

### Requirement: Write file content

The server SHALL provide a `write_file` tool that accepts `path`, `content`, and optional `etag` parameters. It SHALL create or update the file and return `path`, `etag` (new), and `size`.

When `etag` is provided, the server SHALL send an `If-Match` header to the Graph API. If the file has been modified since the provided ETag, the server SHALL return a conflict error.

When `etag` is omitted, the server SHALL overwrite the file without conflict checking.

For files larger than 4MB, the server SHALL use the Graph API upload session mechanism.

#### Scenario: Create a new file
- **WHEN** agent calls `write_file(path="/Documents/new-report.md", content="# Report\n...")`
- **THEN** server creates the file via `PUT /me/drive/root:/Documents/new-report.md:/content` and returns path, etag, and size

#### Scenario: Update with valid ETag
- **WHEN** agent calls `write_file(path="/Documents/report.md", content="updated", etag="abc123")`
- **AND** the file's current ETag matches `"abc123"`
- **THEN** server updates the file and returns the new etag

#### Scenario: Update with stale ETag (conflict)
- **WHEN** agent calls `write_file(path="/Documents/report.md", content="updated", etag="old-etag")`
- **AND** the file's current ETag does not match
- **THEN** server returns an error with `"error": "conflict"` and includes the current etag

#### Scenario: Update without ETag (force overwrite)
- **WHEN** agent calls `write_file` without an etag parameter
- **THEN** server overwrites the file regardless of its current version

### Requirement: Delete a file

The server SHALL provide a `delete_file` tool that accepts a `path` parameter and permanently deletes the file. It SHALL return `{"success": true}`.

#### Scenario: Delete an existing file
- **WHEN** agent calls `delete_file(path="/Documents/old-report.md")`
- **THEN** server calls `DELETE /me/drive/root:/Documents/old-report.md` and returns success

#### Scenario: Delete non-existent file
- **WHEN** agent calls `delete_file` on a path that does not exist
- **THEN** server returns an error with `"error": "not_found"`

### Requirement: Get file info without content

The server SHALL provide a `file_info` tool that accepts a `path` parameter and returns file metadata without downloading content: `name`, `path`, `type`, `size`, `modified`, `etag`, `mime_type`.

#### Scenario: Get info for an existing file
- **WHEN** agent calls `file_info(path="/Documents/report.md")`
- **THEN** server returns metadata from `GET /me/drive/root:/Documents/report.md`

#### Scenario: Get info for a folder
- **WHEN** agent calls `file_info(path="/Documents")`
- **THEN** server returns metadata with `type: "folder"`

### Requirement: Create a folder

The server SHALL provide a `create_folder` tool that accepts a `path` parameter and creates the folder (including intermediate folders). It SHALL return `{"path": "<created path>"}`.

#### Scenario: Create a new folder
- **WHEN** agent calls `create_folder(path="/Documents/Reports/2024")`
- **THEN** server creates the folder hierarchy and returns the path

#### Scenario: Create folder that already exists
- **WHEN** agent calls `create_folder` on an existing folder path
- **THEN** server returns success (idempotent)

### Requirement: Move or rename a file

The server SHALL provide a `move_file` tool that accepts `source` and `destination` path parameters. It SHALL move the file via the Graph API `PATCH` endpoint and return `{"path": "<new path>"}`.

#### Scenario: Move a file to a different folder
- **WHEN** agent calls `move_file(source="/Documents/report.md", destination="/Archive/report.md")`
- **THEN** server moves the file and returns the new path

#### Scenario: Rename a file
- **WHEN** agent calls `move_file(source="/Documents/report.md", destination="/Documents/final-report.md")`
- **THEN** server renames the file and returns the new path
