import { describe, expect, it, vi } from "vitest";

import { ObsidianVaultGateway } from "../../../../src/adapters/outbound/vault/ObsidianVaultGateway";
import { NotePath } from "../../../../src/domain/value-objects/NotePath";
import { createMockApp } from "./mockApp";

describe("ObsidianVaultGateway", () => {
  it("lists only markdown files and skips invalid paths", async () => {
    const mock = createMockApp([
      { path: "a.md", content: "a" },
      { path: "img.png", content: "bin" },
      { path: "notes/b.md", content: "b" },
    ]);
    mock.addFile("dotdot.md", "bad");
    const evil = mock.files.get("dotdot.md")!;
    evil.path = "../escape.md";

    const gateway = new ObsidianVaultGateway(mock.app);
    const listed = await gateway.listMarkdownFiles();
    expect(listed.map((p) => p.value).sort()).toEqual(["a.md", "notes/b.md"]);
  });

  it("reads file content with mtime and sizeBytes", async () => {
    const mock = createMockApp([{ path: "note.md", content: "hello", mtime: 1_700_000_000_000 }]);
    const gateway = new ObsidianVaultGateway(mock.app);
    const snap = await gateway.readFile(NotePath.create("note.md"));
    expect(snap.content).toBe("hello");
    expect(snap.sizeBytes).toBe(5);
    expect(snap.modifiedAt.getTime()).toBe(1_700_000_000_000);
  });

  it("isolates per-file read failures during snapshot", async () => {
    const mock = createMockApp([
      { path: "ok.md", content: "ok" },
      { path: "bad.md", content: "__THROW__" },
      { path: "also.md", content: "also" },
    ]);
    const gateway = new ObsidianVaultGateway(mock.app, { batchSize: 1 });
    const snap = await gateway.getVaultSnapshot();
    expect(snap.map((s) => s.path.value).sort()).toEqual(["also.md", "ok.md"]);
  });

  it("skips ignored folders during snapshot walk and does not read them", async () => {
    const mock = createMockApp([
      { path: "notes/a.md", content: "a" },
      { path: "Templates/x.md", content: "ignored" },
      { path: ".obsidian/app.md", content: "system" },
    ]);
    const gateway = new ObsidianVaultGateway(mock.app);
    const snap = await gateway.getVaultSnapshot(undefined, ["Templates/", ".obsidian/"]);
    expect(snap.map((s) => s.path.value)).toEqual(["notes/a.md"]);
    expect(mock.readPaths).toEqual(["notes/a.md"]);
  });

  it("yields between snapshot batches", async () => {
    const mock = createMockApp(
      Array.from({ length: 5 }, (_, i) => ({ path: `n${i}.md`, content: `c${i}` })),
    );
    const yieldFn = vi.fn(async () => {
      mock.yieldCount.value += 1;
    });
    const gateway = new ObsidianVaultGateway(mock.app, { batchSize: 2, yieldFn });
    await gateway.getVaultSnapshot();
    expect(yieldFn).toHaveBeenCalledTimes(2);
  });

  it("maps vault events for markdown only and clears all listeners on unsubscribe", async () => {
    const mock = createMockApp([
      { path: "a.md", content: "a" },
      { path: "pic.png", content: "p" },
    ]);
    const gateway = new ObsidianVaultGateway(mock.app);
    const events: string[] = [];
    const unsub = gateway.subscribe((event) => {
      events.push(
        event.type === "rename"
          ? `rename:${event.previousPath.value}->${event.path.value}`
          : `${event.type}:${event.path.value}`,
      );
    });

    mock.emitVault("modify", "a.md");
    mock.emitVault("modify", "pic.png");
    mock.addFile("b.md", "b");
    mock.emitVault("create", "b.md");
    mock.emitRename("a.md", "a2.md");

    expect(events).toEqual(["modify:a.md", "create:b.md", "rename:a.md->a2.md"]);

    unsub();
    events.length = 0;
    mock.addFile("c.md", "c");
    mock.emitVault("create", "c.md");
    expect(events).toEqual([]);
  });

  it("reports active note/folder and subscribeActiveFile updates", () => {
    const mock = createMockApp([{ path: "folder/note.md", content: "n" }]);
    const gateway = new ObsidianVaultGateway(mock.app);
    expect(gateway.getActiveNotePath()).toBeNull();

    const seen: Array<string | null> = [];
    const unsub = gateway.subscribeActiveFile((path) => {
      seen.push(path?.value ?? null);
    });

    mock.setActiveFile("folder/note.md");
    mock.emitActiveLeafChange();
    expect(gateway.getActiveNotePath()?.value).toBe("folder/note.md");
    expect(gateway.getActiveFolderPath()?.value).toBe("folder");
    expect(seen).toEqual(["folder/note.md"]);

    mock.setActiveFile(null);
    mock.emitActiveLeafChange();
    expect(gateway.getActiveNotePath()).toBeNull();
    expect(seen).toEqual(["folder/note.md", null]);
    unsub();
  });
});
