# Task Completion Checklist

When a task is completed, ensure the following:

1. **Run tests**: `pytest tests/ -v` — all 68+ tests must pass
2. **Check consistency**: Tool schemas and response formats must match the google-drive-mcp-server
3. **Verify error handling**: All tool handlers must catch `GraphAPIError` and return structured responses
4. **No secrets**: Never commit OAuth tokens or credentials
5. **Type hints**: All new/modified function signatures must have type hints
6. **Follow existing patterns**: Match the style of surrounding code
