# Mark-LII — Project Overview

Mark-LII ("JARVIS") is a cross-platform, real-time voice AI assistant built on Google's
Gemini Live API. It listens, speaks, sees the screen/webcam, and can drive the host
computer through a plugin-based tool system. This repository is currently on branch
`hardening/safe-local-voice`, which locks the assistant down to a minimal, safe
configuration for local voice testing (see **Current Mode: Safe Local Voice**, below).

## Layout

| Path | Purpose |
|---|---|
| `main.py` | Core event loop: Gemini Live session, audio streaming, tool dispatch (`JarvisLive._execute_tool`) |
| `ui.py` | Desktop HUD (waveform, arc-reactor core, theming, panels) |
| `core/` | `llm_client`, `stt`/`tts`, `safe_mode` (tool allow-list gate), `confirm` (irreversible-action gate), `undo`, `plugin_loader`, `audio_devices`, `installer` |
| `actions/` | Individual tool implementations (file I/O, browser/desktop/computer control, web search, weather, reminders, messaging, YouTube, flight lookup, code helper, system/hardware monitor, etc.) |
| `plugins/` | Drop-in `.py` files that extend the assistant with new tools without touching core |
| `memory/` | `memory_manager` (long-term fact store, `long_term.json`) and `config_manager` |
| `dashboard/` | Remote phone-control web dashboard (`server.py` + static assets) |
| `config/` | API keys and static assets |

## Current Mode: Safe Local Voice

`core/safe_mode.py` sets `SAFE_LOCAL_MODE = True`. Every tool call passes through a single
dispatch choke point in `main.py` (`JarvisLive._execute_tool`, line ~1003) that checks the
requested tool name against `ALLOWED_TOOLS` **before** it runs. This is a code-level gate,
not a prompt instruction, so the model cannot talk its way past it.

While active:
- **Allowed tools:** `weather_report`, `web_search` only.
- **Blocked:** file access, browser/desktop/computer control, messaging, code execution,
  the plugin system, the remote dashboard, background monitoring, scheduled tasks/reminders,
  and anything else not explicitly allow-listed. Blocked calls return `BLOCKED_MESSAGE`
  ("This action is disabled in safe local mode.") instead of executing.
- Voice conversation itself (audio in/out, transcription) is unaffected — only *tool calls*
  the model can trigger are gated.

To re-enable a capability, each disabled surface must be reviewed individually and added
back to `ALLOWED_TOOLS` — flipping `SAFE_LOCAL_MODE` to `False` restores everything at once
and is explicitly discouraged by the code comment until that review happens.

## What the Agent Is Capable of (full build, safe mode off)

- Real-time, low-latency voice conversation in any language via Gemini Live API, with
  affective (emotion-aware) tone and proactive audio (ignores background chatter not
  directed at it).
- Persistent, unbounded long-term memory with on-demand recall (`recall_memory`), a UI
  panel to view/delete stored facts, and a budgeted prompt core so the store's size never
  inflates every request.
- Undo for reversible actions: file move/rename/create/copy/write/delete, desktop
  organization, and settings changes (volume, brightness, dark mode).
- Human-in-the-loop confirmation for irreversible actions (shutdown, restart, Wi-Fi
  toggle) — the UI issues the confirmation token, not the model.
- System/computer control: launching apps, volume/brightness, Wi-Fi, shortcuts, power.
- Vision: real-time screen capture and webcam frames piped into the live session.
- Web search (news/research/price/compare/search modes), weather, flight lookup, game
  update triggers (Steam/Epic), file reading/summarizing, inline code help, browser
  control, messaging (WhatsApp/Telegram/etc.), YouTube control, desktop/window management.
- Proactive behavior: morning briefing, time-aware check-ins, background topic
  monitoring, hardware telemetry alerts.
- Extensibility via a single-file plugin system, a remote phone dashboard, and OS-level
  auto-start/scheduled reminders.

## Limitations

**Limitations of the assistant:**
- In this branch's default configuration (`SAFE_LOCAL_MODE = True`), almost all of the
  above is disabled — only weather lookups and web search work as tool calls.
- Undo does not cover files over 1 MB (contents aren't buffered), and settings undo only
  works where the platform can report the pre-change value first.
- Session-resumption state is kept in memory only (not persisted to disk) by design, so a
  full restart of the app starts a fresh session rather than continuing yesterday's chat.
- Audio device selection is stored by name and falls back to the system default if the
  saved device disappears; it does not guarantee output was actually audible beyond the
  one-time startup probe.
- Depends on external services (Gemini Live API, and whichever backends individual
  `actions/` modules call, e.g. search/weather/flight/messaging providers) — behavior is
  bounded by those APIs' availability, rate limits, and terms.
