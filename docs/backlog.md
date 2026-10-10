1. Add anonymised card number

1. Refactor config: unify `source` and `archiving` under a single top-level `mode` key (e.g. `mode: gdrive`) so switching between local and GDrive doesn't require changing `type` in two separate sections

1. automate making input files (ui automation)
    - configurable accounts
    - don't save if no records


1. Documentation update
    - Agents.md file (with Claude, Angtigravity symlinks)
    - Table with specifics for each implementation (similar to Citadele design)

1. Migrate under services, replace tool specific functionality with tool logic (or moved it there)