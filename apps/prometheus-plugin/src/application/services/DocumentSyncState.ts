import { DocumentId } from "../../domain/value-objects/DocumentId";
import type { NotePath } from "../../domain/value-objects/NotePath";

export type DocumentSyncRecord = {
  readonly documentId: DocumentId;
  readonly path: NotePath;
  readonly contentHash: string;
  readonly revision: number;
};

/**
 * In-memory path ↔ DocumentId, hash, and revision ledger for sync/rename.
 * New files use DocumentId.fromNotePath; rename preserves the previous ID.
 */
export class DocumentSyncState {
  private readonly byPath = new Map<string, DocumentSyncRecord>();
  private readonly byDocumentId = new Map<string, DocumentSyncRecord>();

  getByPath(path: NotePath): DocumentSyncRecord | null {
    return this.byPath.get(path.value) ?? null;
  }

  getByDocumentId(documentId: DocumentId): DocumentSyncRecord | null {
    return this.byDocumentId.get(documentId.value) ?? null;
  }

  resolveOrCreate(path: NotePath): DocumentId {
    const existing = this.byPath.get(path.value);
    if (existing) {
      return existing.documentId;
    }
    return DocumentId.fromNotePath(path);
  }

  upsert(record: DocumentSyncRecord): void {
    const previous = this.byDocumentId.get(record.documentId.value);
    if (previous && previous.path.value !== record.path.value) {
      this.byPath.delete(previous.path.value);
    }
    this.byPath.set(record.path.value, record);
    this.byDocumentId.set(record.documentId.value, record);
  }

  removeByPath(path: NotePath): DocumentSyncRecord | null {
    const record = this.byPath.get(path.value) ?? null;
    if (!record) {
      return null;
    }
    this.byPath.delete(path.value);
    this.byDocumentId.delete(record.documentId.value);
    return record;
  }

  nextRevision(path: NotePath): number {
    const existing = this.byPath.get(path.value);
    return existing ? existing.revision + 1 : 1;
  }

  entries(): readonly DocumentSyncRecord[] {
    return [...this.byPath.values()];
  }
}
