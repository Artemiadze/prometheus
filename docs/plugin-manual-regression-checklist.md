# Plugin manual regression checklist (PLG-86)

Manual smoke checklist before a Prometheus Obsidian plugin release.
Run on **Windows**, **Linux**, and **macOS**. Record results in the release task
(pass / fail / N/A + notes + OS + Obsidian version).

## Environment

- [ ] Fresh vault (or dedicated test vault) with at least 20 Markdown notes
- [ ] Ollama installed; for ordinary laptops prefer
      `qwen3:4b-instruct-2507-q4_K_M` (`ollama pull qwen3:4b-instruct-2507-q4_K_M`),
      then select it in Chat / Settings (runtime default tag is still `qwen3:4b`
      until the user picks a model)
- [ ] Plugin built from the release tag (`make plugin-build` / Community Plugin zip)

## Onboarding

- [ ] First enable shows onboarding when `hasCompletedOnboarding` is false
- [ ] Install / download runtime completes or shows a clear error
- [ ] Runtime starts and status becomes ready
- [ ] Initial vault sync completes (or cancel works mid-sync)
- [ ] Selecting a model from Chat composer persists after Obsidian reload
- [ ] Completing onboarding does not re-open on next launch

## Indexing

- [ ] Status panel shows document / chunk counts after sync
- [ ] Editing a note triggers auto-index (when enabled) within debounce window
- [ ] Ignored folders are skipped in snapshot and status counts
- [ ] Manual reindex from Status / Settings completes
- [ ] Cancel active indexing job stops progress and returns UI to idle
- [ ] File menu **Reindex this note in Prometheus** updates that note only

## Chat

- [ ] Open Chat from ribbon / command palette
- [ ] New chat tab (+), switch tabs, close tab (always at least one tab remains)
- [ ] Model picker in composer lists local models; selection updates Status LLM row
- [ ] Scope pill (Auto / Vault / Current note / Current folder) affects retrieval
- [ ] Short question (under 3 characters after trim) shows validation error (too short)
- [ ] Valid question streams / returns an answer with sources
- [ ] Copy message on user question and assistant answer copies the message text
- [ ] Insufficient-context answer shows the hint, not a hard failure
- [ ] Opening a source navigates to the note (and heading when present)
- [ ] Cancel mid-request returns to idle without a stuck spinner
- [ ] File menu **Ask Prometheus about this note** pins scope for one message

## Search

- [ ] Open Search from command palette
- [ ] Queries under 3 characters show too-short state
- [ ] Valid query shows results; nonsense query shows empty state
- [ ] Scope modes (vault / note / folder) change results as expected
- [ ] File menu **Search this folder in Prometheus** pins folder scope
- [ ] Opening a hit navigates to the note

## Errors and recovery

- [ ] With runtime stopped, Chat/Search show a recoverable error (install/start CTA)
- [ ] Disable network access → install/update is blocked with Privacy guidance
- [ ] Incompatible runtime version surfaces update guidance (do not hang)
- [ ] Legacy `qdrant/` data under the vault data dir is reported by doctor / status
      with guidance to full reindex (sqlite-vec; no automatic migration)
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
