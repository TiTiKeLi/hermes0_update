# Dashboard Modifier

Modify the Hermes dashboard UI and server. You have permission to edit:
- `C:\Users\Lsc\.hermes\gui.py`  — Python HTTP server (runs inside container)
- `C:\Users\Lsc\.hermes\gui.html` — Single-page HTML/JS frontend
- `C:\Users\Lsc\.hermes\start-dashboard.bat` — Batch launcher

## Architecture

- **Server**: `gui.py` runs **inside the Hermes container** on port 8644
  - `do_GET()` — serves HTML pages and JSON API responses
  - `do_POST()` — handles queries and actions as JSON
  - Helper methods: `get_status()`, `get_memory()`, `get_sessions()`, `get_skills()`, `get_facts()`, `get_health()`
  - All commands run locally inside the container (no `docker exec` needed)
  - Port: 8644 (mapped to host via docker-compose.yml)

- **Frontend**: `gui.html` is a single HTML file with embedded CSS and JS
  - Styles: CSS variables for dark mode, GitHub-style design
  - JS: Vanilla JS with `fetch()` API, modal overlay system
  - Layout: sidebar navigation → tab content (overview, memory, sessions, chat, skills, config, logs)

- **Auto-start**: Container command is `sh -c "python3 /opt/data/gui.py & exec hermes gateway run"`
  - GUI starts automatically with the container
  - Gateway runs in foreground as PID 1

- **Startup**: `start-dashboard.bat` starts GUI (if not running) and opens browser

## How to Add an API Endpoint

1. In `gui.py`, add a new `elif` branch in `do_GET()` or `do_POST()`
2. Create a helper method on the `Handler` class for the logic
3. In `gui.html`, add JS code to call the endpoint and render results

Example - adding a GET endpoint:
```python
elif p == "/api/custom":
    return self.json(self.get_custom_data())

def get_custom_data(self):
    return {"key": "value"}
```

Example - adding a POST endpoint:
```python
elif p == "/api/action":
    action = body.get("action", "")
    if action == "my-action":
        result = run("some-command", 30)
        return self.json({"result": result})
    return self.json({"error": "unknown action"}, 400)
```

## How to Update config.yaml

Use the mounted volume at `/opt/data/config.yaml`:
```python
import yaml
path = DATA / "config.yaml"
cfg = yaml.safe_load(path.read_text())
cfg['model']['default'] = new_model
path.write_text(yaml.dump(cfg, allow_unicode=True, default_flow_style=False))
```

## How to Modify the HTML

- Sidebar navigation is in `<nav class="sidebar">`
- Tab content is in `<div class="tab-content" id="tab-{name}">`
- Modals use `modal-overlay` / `modal` pattern
- Add new UI sections as new `tab-content` divs
- Use existing CSS variables (`--bg`, `--card`, `--accent`, etc.)

## Code Style

- Python: 4-space indent, no type hints, simple functions
- HTML/CSS: GitHub-style dark theme, card-based layout, CSS variables
- JS: Vanilla JS, `async/await` with `fetch()`, no frameworks
- All user-facing text in Chinese

## Container Configuration

docker-compose.yml:
```yaml
services:
  hermes:
    image: hermes-agent:with-deps
    entrypoint: ["sh", "-c"]
    command: ["python3 /opt/data/gui.py & exec hermes gateway run"]
    ports:
      - "8644:8644"
    volumes:
      - C:\Users\Lsc\.hermes:/opt/data
    environment:
      - HTTP_PROXY=
      - HTTPS_PROXY=
      - NO_PROXY=*
```

## Permission

You are authorized to read and write ALL of the above files.
