1. Fill the `Card` (masked, last 4 digits) and `Payment method` (`Card` / `Transfer`) columns for Swedbank and LHV
    - Design (draft): [DESIGN-card-and-payment-method.md](design/DESIGN-card-and-payment-method.md);
      origin: [Tiller columns review 2026-11-12](reviews/BACKLOG-REVIEW-tiller-columns-2026-11-12.md) (K3, F1).
    - The columns exist in the Tiller table and in `schemas/tiller_target.yaml` since 2026-11-12 and are left empty.
    - Effort about 4–5 h: `regex_extract` and `value_map` transformations, optional intermediate fields, 2 bank mappings.

1. ~~Add a `Receipt` column to the Tiller output~~ — structure done 2026-11-12: the Tiller table has `Receipt` and
   `Clarified?`, `schemas/tiller_target.yaml` has both (left empty by the service). Filling them is done by the
   finance-domain financial review, not by the service.

1. Refactor config: unify `source` and `archiving` under a single top-level `mode` key (e.g. `mode: gdrive`) so switching between local and GDrive doesn't require changing `type` in two separate sections

1. automate making input files (ui automation)
    - configurable accounts
    - don't save if no records


1. Documentation update
    - Agents.md file (with Claude, Angtigravity symlinks)
    - Table with specifics for each implementation (similar to Citadele design)

1. Migrate under services, replace tool specific functionality with tool logic (or moved it there)