# Amir's Bug Patterns — Personal Context Library

A curated set of bug patterns from my own projects, organized so I can mechanically apply them to a new project's `CLAUDE.md` / bugbot config and avoid repeating the same mistakes.

## Why this exists

I noticed the same bug classes appearing across multiple projects of mine — different stacks, different problem domains, same underlying mistakes. After three projects' worth of post-mortem documentation (`docs/source-projects/`), I cross-referenced them into a single library.

The bugs split along three axes:
- **Frequency** — how many of my projects exhibited the pattern (signal for "is this me?").
- **Severity** — security, privacy, data loss, financial impact (signal for "must catch regardless").
- **Stack scope** — which technologies / domains the pattern attaches to (signal for "is this relevant here?").

## How to apply to a new project

### 1. Always copy (regardless of stack)

| Source | Destination |
|---|---|
| `CORE-PATTERNS.md` | Drop into `docs/` of the new project, or link from `CLAUDE.md`. |
| `CRITICAL-PATTERNS.md` | Same. |
| `claude-md-snippets/universal.md` | **Paste contents into the project's `CLAUDE.md`** (terse, 6 rules). |
| `claude-md-snippets/critical.md` | **Paste contents into the project's `CLAUDE.md`** (terse, 10 rules). |

That's ~50 lines added to `CLAUDE.md` covering the universal + security baseline.

### 2. Then by stack

Walk this decision tree. Each "yes" copies one stack file + one snippet.

| If the project has… | Copy | Paste into `CLAUDE.md` |
|---|---|---|
| React frontend | `BY-STACK/react-frontend.md` | `claude-md-snippets/react.md` |
| Async SQLAlchemy | `BY-STACK/async-orm.md` | `claude-md-snippets/async-orm.md` |
| Status enums / state machines / touchpoint logic | `BY-STACK/state-machine.md` | `claude-md-snippets/state-machine.md` |
| Webhooks / Pub-Sub / queue consumers | `BY-STACK/webhooks.md` | `claude-md-snippets/webhooks.md` |
| Cron / scheduled tasks | `BY-STACK/cron-jobs.md` | `claude-md-snippets/cron-jobs.md` |
| Postgres (or any SQL with migrations & pagination) | `BY-STACK/postgres.md` | `claude-md-snippets/postgres.md` |
| Anthropic / Google / Stripe / OAuth / FCM SDKs | `BY-STACK/external-sdk.md` | `claude-md-snippets/external-sdk.md` |
| Browser code with `mailto:` / clipboard / blob URLs | `BY-STACK/browser-handoff.md` | `claude-md-snippets/browser-handoff.md` |

### 3. Optional — if time permits

`RECURRING-PATTERNS.md` covers patterns from 2 of 3 source projects (R1–R5). Useful additional context for the long run; not required for the first review pass.

### 4. Bugbot rules

`bugbot-rules/*.md` — one file per rule, stack-agnostic. Use these by either:
- Copying individual files into a Cursor bugbot / similar code-review config.
- Pasting the contents into a Claude code-review prompt one at a time when reviewing a PR.
- Combining several into a single prompt for a directed review (e.g., a security pass = K1..K10 rules).

The CRITICAL-tagged rules (`pii-in-logs`, `xss-innerhtml`, `rate-limit-xff-spoofing`, etc.) should always run on PRs that touch auth, public-facing endpoints, or user input.

## How to maintain

When I encounter a new pattern that wasn't in this library:

1. **Document it under `docs/source-projects/<project-name>-patterns.md`** in the same EmailFlow-style template (P1, P2, ..., with code commits, false positives, recommended mode).

2. **Cross-reference against the existing tiers:**
   - If 3 source documents now confirm the same pattern → promote to `CORE-PATTERNS.md`.
   - If 2 of 3 confirm → `RECURRING-PATTERNS.md`.
   - If severity is HIGH (security, data-loss, privacy) regardless of frequency → `CRITICAL-PATTERNS.md`.
   - Otherwise → relevant `BY-STACK/*.md` only.

3. **Add a `bugbot-rules/<name>.md`** for any pattern with a clean automated detection signature.

4. **Update `claude-md-snippets/*.md`** if the pattern is succinct enough to fit in ≤20 lines.

5. **Re-read `MIGRATION-NOTES.md`** quarterly to see if my mental model of "universal vs stack-specific" still holds.

## Repo layout

```
amir-bug-patterns/
├── README.md                    # this file
├── CORE-PATTERNS.md             # U1..U6 — 3/3 sources, apply everywhere
├── CRITICAL-PATTERNS.md         # K1..K10 — high-severity, apply everywhere
├── RECURRING-PATTERNS.md        # R1..R5 — 2/3 sources, apply if stack matches
├── MIGRATION-NOTES.md           # meta-analysis, top-3 day-1 picks
├── BY-STACK/                    # 8 files, organized by mental model
│   ├── react-frontend.md
│   ├── async-orm.md
│   ├── state-machine.md
│   ├── webhooks.md
│   ├── cron-jobs.md
│   ├── postgres.md
│   ├── external-sdk.md
│   └── browser-handoff.md
├── claude-md-snippets/          # ≤20 lines each, paste into project CLAUDE.md
│   ├── universal.md
│   ├── critical.md
│   ├── react.md
│   ├── async-orm.md
│   ├── state-machine.md
│   ├── webhooks.md
│   ├── cron-jobs.md
│   ├── postgres.md
│   ├── external-sdk.md
│   └── browser-handoff.md
├── bugbot-rules/                # one rule per file, stack-agnostic
│   ├── race-toctou.md
│   ├── react-stale-state-on-prop.md
│   ├── external-input-isinstance.md
│   ├── postgres-null-cas.md
│   ├── linked-field-atomicity.md
│   ├── migration-model-drift.md
│   ├── pagination-tiebreaker.md
│   ├── sdk-error-completeness.md
│   ├── window-open-protocol-handoff.md
│   ├── cron-terminal-state.md
│   ├── filter-too-narrow.md
│   ├── pii-in-logs.md                       # CRITICAL
│   ├── secret-in-error-response.md          # CRITICAL
│   ├── xss-innerhtml.md                     # CRITICAL
│   ├── rate-limit-xff-spoofing.md           # CRITICAL
│   ├── auth-before-irreversible-action.md   # CRITICAL
│   ├── privilege-escalation-unverified.md   # CRITICAL
│   ├── network-exposed-without-auth.md      # CRITICAL
│   └── like-wildcard-injection.md           # CRITICAL
└── docs/source-projects/        # original post-mortem docs (reference)
    ├── noa-leads-patterns.md
    ├── emailflow-patterns.md
    └── eight-projects-patterns.md
```

## See also

- **`MIGRATION-NOTES.md`** — what surprised me during the cross-reference, and the top-3 patterns to wire into a new project on day one.
- **`docs/source-projects/`** — the original Hebrew post-mortem documents that feed this library. The cross-references in every pattern file (`commit 33af59e`, `commit f847a44`, etc.) point into these source docs.
