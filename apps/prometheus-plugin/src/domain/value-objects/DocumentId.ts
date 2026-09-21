import { createHash } from "node:crypto";

import { InvalidIdentifierError } from "../errors";
import type { NotePath } from "./NotePath";

const DOCUMENT_ID = /^[A-Za-z0-9][A-Za-z0-9_-]{5,127}$/;

/**
 * Opaque stable document ID, optionally derived from a normalized NotePath.
 * fromNotePath must match runtime DocumentId.from_relative_path (sha256 hex[:32]).
 */
export class DocumentId {
  readonly value: string;

  private constructor(value: string) {
    this.value = value;
  }

  static create(value: string): DocumentId {
    if (!DOCUMENT_ID.test(value)) {
      throw new InvalidIdentifierError();
    }
    return new DocumentId(value);
  }

  static fromNotePath(path: NotePath): DocumentId {
    const digest = createHash("sha256").update(path.value, "utf8").digest("hex");
    return DocumentId.create(digest.slice(0, 32));
  }

  toString(): string {
    return this.value;
  }
}
