# Suggested Commands

## Development Setup
```bash
pip install -e ".[dev]"
```

## Run Server Locally
```bash
python -m onedrive_mcp.server
# or with explicit PYTHONPATH:
PYTHONPATH=src python -m onedrive_mcp.server
```
Server starts on `http://localhost:8080` by default. Override with `PORT` env var.

## Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_graph_client.py -v
pytest tests/test_auth.py -v
pytest tests/test_tools.py -v
pytest tests/test_health.py -v
```
All tests use mocked HTTP via `respx` — no Microsoft account or network needed.

## Docker
```bash
# Build
docker build -t one-drive-mcp-server .

# Run
docker run -p 8080:8080 one-drive-mcp-server

# Docker Compose
docker-compose up --build
```

## Useful System Commands (macOS/Darwin)
```bash
git status / git diff / git log --oneline
ls -la
find . -name "*.py" -not -path "./.git/*"
grep -rn "pattern" src/
```
