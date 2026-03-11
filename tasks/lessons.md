# Lessons

- When updating a skill, keep `SKILL.md`, bundled references, agent metadata, and executable scripts in sync; a good spec with stale implementation is still a broken skill.
- For API-backed skills, add regression tests around provider constraints and execution gating so unsupported parameters and unintended paid calls fail locally before release.
- When a user provides a canonical external spec URL, treat that URL as the source of truth and re-check any prior interpretation before hard-coding workflow changes.
