# AGENTS.md

## Agent & Subagent Rules

### Subagent Spawning Constraint (CRITICAL)
- **Do NOT spawn headless background subagents (`invoke_subagent`)**: Headless subagents do not provide UI cards in T3 Code, cannot be monitored or supervised in real time by the user, and do not provide wake notifications.
- **Execute directly in the active thread**: All orchestration, implementation, debugging, verification, and documentation work must be carried out directly in the main thread so the user has full transparency, oversight, and control.
- **Delegation only upon explicit user instruction**: If the user explicitly asks for delegated child tasks, use visible T3 Code tasks (`delegate_task` / `t3_thread_launch`) with dedicated cards, never unmonitored background subagents.
