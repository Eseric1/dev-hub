# dev://hub — Personal Project Navigator

A local micro-frontend hub for managing isolated personal projects.
Each project runs on its own port with no shared logic or state.

Built as a learning project while transitioning from semiconductor
equipment technician toward quantum hardware manufacturing.

---

## Structure

```
dev-hub/
├── hub/                    # Navigator shell
│   ├── index.html          # Project launcher dashboard
│   └── projects.json       # Project registry manifest
│
├── file-explorer/          # Local filesystem browser
│   ├── index.html          # Frontend UI
│   ├── explorer.py         # Secured HTTP server
│   └── launch.py           # System tray launcher
│
├── field-intel/            # Technical observation logger
│   └── index.html          # Entry capture + log feed
│
└── shared/
    └── server-utils.ps1    # PowerShell utility layer
```

---

## Architecture

Each project is isolated — its own server, its own port, its own storage.
The hub knows where each project lives via `projects.json` but does not
control their logic.

```
hub (navigator)
├── file-explorer  → random port, token-authenticated
└── field-intel    → standalone, localStorage
```

`server-utils.ps1` provides the system layer:
- `Get-FreePort` — find an available TCP port
- `New-SecretToken` — cryptographic token generation
- `Test-PortReady` — TCP polling until server accepts connections
- `Get-ProjectRegistry` — read project manifest
- `Get-FileMetadata` — rich file/folder metadata objects

Python launchers call these PowerShell functions rather than reimplementing
the same logic — right tool for the right job.

---

## Projects

### fs:// explorer
Local file system browser. Drag-and-drop upload, favorites, search.
Secured: 127.0.0.1 only, per-session token, rate limiting, path traversal prevention.

### field://intel
Personal observation logger for technical environments.
Categories: chemical delivery, sensors, mechanical, electrical, software, PM.
Keyboard shortcut: `Ctrl+Enter` to save entry.

---

## Why this exists

I work as an equipment technician in semiconductor wet etch.
I built this to:
1. Have a clean way to navigate personal dev projects locally
2. Practice PowerShell as a system utility layer alongside Python
3. Build the logging habit — capturing technical observations deliberately

The field intel logger is the most important piece.
Every observation stored there is interview material.

---

## Roadmap

- [ ] Hub server (Python) — launch projects from the hub directly
- [ ] PowerShell query scripts — pipeline observations to CSV reports  
- [ ] Pattern dashboard — visualize observation coverage over time
- [ ] Export to markdown — generate study notes from log entries