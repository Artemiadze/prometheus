import { describe, expect, it } from "vitest";

import { InvalidIdentifierError, InvalidPathError } from "../errors";
import { DocumentId } from "./DocumentId";
import { NotePath } from "./NotePath";
import { VaultId } from "./VaultId";

describe("NotePath", () => {
  it("normalizes backslashes and collapses empty and dot segments", () => {
    expect(NotePath.create("notes\\example.md").value).toBe("notes/example.md");
    expect(NotePath.create("notes/./example.md").value).toBe("notes/example.md");
    expect(NotePath.create("notes//example.md").value).toBe("notes/example.md");
  });

  it("rejects absolute, drive-prefixed, empty, and escaping paths", () => {
    expect(() => NotePath.create("/absolute.md")).toThrow(InvalidPathError);
    expect(() => NotePath.create("C:/Vault/note.md")).toThrow(InvalidPathError);
    expect(() => NotePath.create("")).toThrow(InvalidPathError);
    expect(() => NotePath.create("../secret.md")).toThrow(InvalidPathError);
    expect(() => NotePath.create("notes/../../escape.md")).toThrow(InvalidPathError);
    expect(() => NotePath.create("notes/\0evil.md")).toThrow(InvalidPathError);
  });

  it("exposes name and parent", () => {
    const path = NotePath.create("folder/sub/note.md");
    expect(path.name).toBe("note.md");
    expect(path.parent?.value).toBe("folder/sub");
    expect(NotePath.create("root.md").parent).toBeNull();
  });
});

describe("VaultId", () => {
  it("accepts path-segment-safe ids", () => {
    expect(VaultId.create("vault-abc").value).toBe("vault-abc");
  });

  it("rejects invalid identifiers", () => {
    expect(() => VaultId.create("AB")).toThrow(InvalidIdentifierError);
    expect(() => VaultId.create("UpperCase")).toThrow(InvalidIdentifierError);
    expect(() => VaultId.create("a")).toThrow(InvalidIdentifierError);
  });
});

describe("DocumentId", () => {
  it("accepts opaque ids matching the runtime pattern", () => {
    expect(DocumentId.create("abcdef").value).toBe("abcdef");
  });

  it("rejects short or illegal identifiers", () => {
    expect(() => DocumentId.create("abc")).toThrow(InvalidIdentifierError);
    expect(() => DocumentId.create("has space")).toThrow(InvalidIdentifierError);
  });

  it("derives a deterministic id from a note path (runtime interop)", () => {
    const a = DocumentId.fromNotePath(NotePath.create("notes/example.md"));
    const b = DocumentId.fromNotePath(NotePath.create("notes\\example.md"));
    expect(a.value).toBe("8dab38202ad5573d4bb137ad9653dfa2");
    expect(b.value).toBe(a.value);

    const c = DocumentId.fromNotePath(NotePath.create("Folder/Note.md"));
    expect(c.value).toBe("25f3d35e3c78fe8816cd66be70038769");
  });
});
