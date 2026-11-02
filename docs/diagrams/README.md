# Diagrams

Mermaid sources for the deck and the docs. Render with any Mermaid-capable
viewer (VS Code Markdown preview, GitHub, mermaid.live) or the Mermaid CLI if it
is installed:

```powershell
npx -y @mermaid-js/mermaid-cli -i docs/diagrams/target_architecture.mmd -o docs/diagrams/target_architecture.svg
```

| File | Shows | Used in |
|---|---|---|
| `research_pipeline.mmd` | research → matrix → taxonomy → gap → blueprint → Gate 1 | strategy/README, manager pack |
| `landscape_map.mmd` | the four layers and the representative tools in each | strategy/industry_map |
| `two_angles.mmd` | authoring angle vs consumption angle, storage as a side box | strategy/better_version_blueprint, deck |
| `target_architecture.mmd` | sources → four layers → review gate → API/MCP → agents | blueprint, deck |
| `coverage_map.mmd` | automatic vs confidence vs human approval vs impossible | blueprint, HITL discussion |
| `roadmap.mmd` | research, Gate 1, build, Gate 2 timeline | plan, manager updates |

The same diagrams are also written as ASCII in the Markdown documents, so the
pack reads correctly even where Mermaid is not rendered.
