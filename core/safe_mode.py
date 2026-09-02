"""
Central switch for Mark-LII's "Safe Local Voice" hardening mode.

While SAFE_LOCAL_MODE is True, every tool call is checked against ALLOWED_TOOLS
at the single dispatch boundary in main.py's JarvisLive._execute_tool — this is
a code-level gate, not a prompt instruction, so the model cannot talk its way
past it. Everything not explicitly listed (file access, computer/browser
control, messaging, code execution, plugins, the remote dashboard, background
monitoring, scheduled tasks, ...) is refused before it can run.

Flip SAFE_LOCAL_MODE to False only after each disabled surface listed in the
hardening review has been re-enabled and reviewed individually.
"""
from __future__ import annotations

SAFE_LOCAL_MODE = True

# Tool names permitted through the central dispatch gate while SAFE_LOCAL_MODE
# is on. Voice conversation itself (audio in/out, transcription) is not a tool
# call and is unaffected; this list only covers function/tool calls the model
# can trigger.
ALLOWED_TOOLS = frozenset({
    "weather_report",
    "web_search",
})

BLOCKED_MESSAGE = "This action is disabled in safe local mode."
