"""PreToolUse/Bash guard: block commands that would print secret VALUES
(AGENTS.md sec.16). Variable names are fine; values must stay in .env and the
operator environment. .env.example carries no values and stays readable."""
import json
import re
import sys

# `.env` / `.env.local` etc, but never `.env.example`.
DOTENV = r"\.env(?!\.example)(\.[a-z0-9_-]+)?\b"

READERS = r"(cat|type|less|more|head|tail|bat|strings|xxd|od|Get-Content|gc)"

# grep with a counting flag prints no values, so it stays allowed.
COUNT_FLAG = r"(\s-[a-z]*c\b|--count\b)"

SECRET_VARS = (
    r"(GOOGLE_CLIENT_SECRET|SESSION_SECRET|CLOUDFLARE_TUNNEL_TOKEN|POSTGRES_PASSWORD"
    r"|POSTGRES_RUNTIME_URL|POSTGRES_SHADOW_URL|OPENAI_API_KEY|DEEPSEEK_API_KEY"
    r"|SUPADATA_API_KEY|GROQ_API_KEY|AZURE_SPEECH_KEY|GOOGLE_CLIENT_ID)"
)

RULES = [
    (rf"\b{READERS}\b[^|;&]*{DOTENV}",
     "This prints `.env` secret values. AGENTS.md 16 forbids printing, committing, or "
     "documenting secret values. Read `.env.example` for the variable names, or check a "
     "single key's presence with `grep -c '^NAME=' .env`."),
    (rf"\bgrep\b(?![^|;&]*{COUNT_FLAG})[^|;&]*{DOTENV}",
     "Grepping `.env` echoes secret values (AGENTS.md 16). Use `grep -c '^NAME=' .env` to "
     "test presence without printing the value."),
    (rf"\b(echo|printf|Write-Host|Write-Output)\b[^|;&]*\$\{{?{SECRET_VARS}",
     "This echoes a secret value (AGENTS.md 16). Report only that the variable is set."),
    # `docker exec` reaches a container just as well as `docker compose exec`.
    (r"\bdocker\s+(compose\s+)?exec\b[^|;&]*\b(printenv|env)\b(?![^|;&]*\|)",
     "Dumping the container environment exposes secret values (AGENTS.md 16). Query a "
     "single variable's presence instead."),
    # A live API key reached a transcript through
    # `docker inspect --format '{{range .Config.Env}}...'`. The env block is the
    # same secret material as `.env`, however it is reached.
    (r"\bdocker\s+inspect\b[^|;&]*\.Env\b",
     "Formatting a container's env block prints secret values (AGENTS.md 16). Ask for "
     "the field you actually need, or test one variable's presence without printing "
     "it."),
    # No --format means the whole config document, env block included.
    (r"\bdocker\s+inspect\b(?![^|;&]*(--format|-f\b))",
     "A bare `docker inspect` dumps the entire container config, including the env "
     "block and its secret values (AGENTS.md 16). Name the field instead, e.g. "
     "`docker inspect NAME --format '{{.HostConfig.PortBindings}}'`."),
    (rf"\b{READERS}\b[^|;&]*\b(auth\.json|credentials\.json|id_rsa|\.pem)\b",
     "This prints credential material (AGENTS.md 16)."),
]


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    for pattern, reason in RULES:
        if re.search(pattern, command, re.IGNORECASE):
            json.dump({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }, sys.stdout)
            return


main()
