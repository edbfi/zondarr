# Zondarr Backend

Unified invitation and user management system for media servers (Plex, Jellyfin).

## Development

```bash
# Install dependencies
uv sync

# Run development server (Granian, through litestar-granian's GranianPlugin)
uv run litestar --app zondarr.app:app run --host 0.0.0.0 --port 8000

# Type checking
basedpyright

# Linting and formatting
ruff check .
ruff format .

# Run tests
pytest
```
