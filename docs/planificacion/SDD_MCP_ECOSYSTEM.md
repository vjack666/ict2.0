# SDD — MCP Ecosystem for OpenCode and Hermes

**Project:** `ict2.0`  
**Status:** local clients normalized to `ict2.0`; Hermes Mission Controller adapter pending MC-3  
**Authority:** `.hermes/` and `docs/planificacion/SDD_HERMES_MISSION_CONTROLLER.md`

## Purpose

Provide one shared MCP boundary for:

- **Context7:** current library and API documentation lookup.
- **Engram:** persistent project memory shared by OpenCode and Hermes.

The MCP layer does not become the authority for mission state. Hermes keeps
durable mission state in `.hermes-state/`; Engram stores decisions,
discoveries, warnings, sessions and outcomes.

## Canonical project identity

The repository is identified as `ict2.0`. Both clients must use this explicit
project key so memory is not split between `ict-system`, a directory name, or a
different working directory.

## Client bindings

| Client | Configuration | Status |
|---|---|---|
| OpenCode | `opencode.json` + global OpenCode config | Active; project `ict2.0` |
| Hermes | `%LOCALAPPDATA%/hermes/config.yaml` + `.hermes/mcp_servers.yaml` | Config normalized; restart required; project `ict2.0`; built-in memory disabled |
| Codex | `%USERPROFILE%/.codex/config.toml` | Engram active; project `ict2.0` |
| Claude Code | `%USERPROFILE%/.claude/mcp/engram.json` | Engram active; project `ict2.0` |
| Cursor | `%USERPROFILE%/.cursor/mcp.json` | Engram active; project `ict2.0` |
| VS Code | `%APPDATA%/Code/User/mcp.json` | Engram active; project `ict2.0` |
| Continue | `%USERPROFILE%/.continue/config.yaml` | Engram + Context7 configured; project `ict2.0` |
| Aider | `.aider.conf.yml` / CLI | No native MCP binding; filesystem-only fallback |

All local clients use the same Engram binary and explicit project key
`ict2.0`. OpenCode, Codex, Claude Code, Cursor, and VS Code connect over local
stdio; Continue is now configured the same way; Hermes uses the same MCP
definition from its local configuration. Aider does not expose a native MCP
binding in its configuration, so it remains a terminal interface that must
rely on repository files. The repository's `.hermes-state/` remains the
mission-state authority.

## Safety policy

- Context7 is a documentation lookup service only.
- Engram is memory, not mission state and not a permission authority.
- Hermes built-in `MEMORY.md`/`USER.md` memory is disabled; those files are
  retained as historical data and are not authoritative.
- The Engram app installed in ChatGPT/Codex is account-level memory and is not
  synchronized with the local Engram database; it is not canonical for this
  machine.
- No API key is stored in the repository.
- No MCP server may execute trades or mutate the production market engine.
- Candidate engine changes remain subject to the laboratory gates and human
  promotion approval.

## Verification

```powershell
opencode mcp list
engram doctor --project ict2.0 --json
engram context ict2.0
```

Expected result: both MCP servers connected and Engram diagnostics without a
project/directory mismatch.
