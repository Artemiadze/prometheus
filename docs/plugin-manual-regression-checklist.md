# Plugin manual regression checklist (PLG-86)

Manual smoke checklist before a Prometheus Obsidian plugin release.
Run on **Windows**, **Linux**, and **macOS**. Record results in the release task
(pass / fail / N/A + notes + OS + Obsidian version).

## Environment

- [ ] Fresh vault (or dedicated test vault) with at least 20 Markdown notes
- [ ] Ollama installed with the default model from Settings
- [ ] Plugin built from the release tag (`make plugin-build` / Community Plugin zip)

## Onboarding

- [ ] First enable shows onboarding when `hasCompletedOnboarding` is false
- [ ] Install / download runtime completes or shows a clear error
- [ ] Runtime starts and status becomes ready
- [ ] Initial vault sync completes (or cancel works mid-sync)
- [ ] Selecting a model persists after Obsidian reload
- [ ] Completing onboarding does not re-open on next launch

## Indexing

- [ ] Status panel shows document / chunk counts after sync
- [ ] Editing a note triggers auto-index (when enabled) within debounce window
- [ ] Ignored folders are skipped in snapshot and status counts
- [ ] Manual reindex from Status / Settings completes
- [ ] Cancel active indexing job stops progress and returns UI to idle

## Chat

- [ ] Open Chat from ribbon / command palette
- [ ] Short question shows validation error (too short)
- [ ] Valid question streams / returns an answer with sources
- [ ] Insufficient-context answer shows the hint, not a hard failure
- [ ] Opening a source navigates to the note (and heading when present)
- [ ] Cancel mid-request returns to idle without a stuck spinner
- [ ] “Ask about this note” from file menu pins scope for one message

## Search

- [ ] Open Search from command palette
- [ ] Queries under 3 characters show too-short state
- [ ] Valid query shows results; nonsense query shows empty state
- [ ] Scope modes (vault / note / folder) change results as expected
- [ ] “Search in folder” from file menu pins folder scope
- [ ] Opening a hit navigates to the note

## Errors and recovery

- [ ] With runtime stopped, Chat/Search show a recoverable error (install/start CTA)
- [ ] Disable network access → install/update is blocked with Privacy guidance
- [ ] Incompatible runtime version surfaces update guidance (do not hang)
- [ ] Diagnostics report opens and redacts note text / session tokens
- [ ] Verbose logging off by default; when on, console has no note body text

## Unload / re-enable

- [ ] Disable plugin: status polling stops, no orphan leaves for Chat/Search/Status
- [ ] Re-enable plugin: panels open cleanly against fresh stores
- [ ] With `runtimeAutostart` off, Obsidian load does not spawn runtime until first use
- [ ] With `runtimeAutostart` on, runtime starts after layout ready

## Sign-off

| OS | Obsidian | Build | Tester | Date | Result |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

Attach this table (or a link) to the release task. Failures block the release until
triaged.
