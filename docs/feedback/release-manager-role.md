# Tool/Service Feedback: financial-transactions-etl

<!-- IMPORTANT: Always add the newest feedback/session entry at the TOP of the file (immediately below this comment). Do not append to the bottom. -->

## Session: 2026-07-02 — Release Manager: Citadele feature release

### 2. Interface & Usage Issues

1. **`docs/tmp/` left untracked after RM pipeline**: The git pipeline writes `git_changes.txt` and `git_diff.txt` to `docs/tmp/`. These are correctly excluded from commits, but `docs/tmp/` stays visible in `git status` as an untracked directory until manually cleaned up. Adds noise to every subsequent `git status` call in the session.

2. **`=7.0.0` shell artifact at repo root**: A `pip install` command without a space (`pip install package=7.0.0` instead of `==`) created a file named `=7.0.0` in the repo root. It appeared in the RM's `git_changes.txt` as `[NEW]` and had to be identified and deleted before staging. Suggests a need for a pre-commit hook or `.gitignore` guard for such artifacts.

3. **Bugfix commit added after release flow**: A real-file pipeline run revealed a correctness bug in `_process_purchase` (PURCHASE TransactionDate used settlement date instead of card swipe date). The fix was prepared and committed in the same RM session, after the two feature commits were already staged. The RM role protocol has no explicit procedure for this scenario.

### 3. Proposed Improvements & Backlog Items

- **BACKLOG**: Add `docs/tmp/` to `.gitignore` to suppress RM pipeline artifacts from `git status`.
- **BACKLOG**: Add a pre-commit hook or `.gitignore` pattern to catch `=N.N.N` shell artifacts at repo root.
- **ROLE PROPOSAL**: Document a "post-release bugfix commit" mini-protocol in `role.md` Phase 5b — stage known files explicitly, skip git pipeline re-run, CR optional per user decision.
