# CLAUDE.md

## Agent & Subagent Rules

- **No headless subagents**: Do not spawn background subagents (`invoke_subagent`). Work directly in the active thread where the user can supervise and monitor all steps in real time. See `AGENTS.md`.

## Agent skills

### Issue tracker

GitHub Issues on MadManJohnSmith/catpart-parser, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical role names as label strings: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` + `docs/adr/` at the repo root (created lazily when terms or decisions get resolved). See `docs/agents/domain.md`.
