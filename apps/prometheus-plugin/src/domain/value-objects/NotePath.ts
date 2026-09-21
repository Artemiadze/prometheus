import { InvalidPathError } from "../errors";

const WINDOWS_DRIVE = /^[A-Za-z]:\//;

/**
 * A normalized POSIX path that cannot escape its Vault.
 * Mirrors runtime RelativePath (PRM-8 / relative_path.py).
 */
export class NotePath {
  readonly value: string;

  private constructor(value: string) {
    this.value = value;
  }

  static create(raw: string): NotePath {
    const normalizedInput = raw.replace(/\\/g, "/");
    if (
      !normalizedInput ||
      normalizedInput.includes("\0") ||
      normalizedInput.startsWith("/") ||
      WINDOWS_DRIVE.test(normalizedInput)
    ) {
      throw new InvalidPathError();
    }

    const parts = normalizedInput.split("/").filter((part: string) => part !== "" && part !== ".");
    if (parts.length === 0 || parts.includes("..")) {
      throw new InvalidPathError();
    }

    return new NotePath(parts.join("/"));
  }

  get name(): string {
    const segments = this.value.split("/");
    return segments[segments.length - 1] ?? this.value;
  }

  get parent(): NotePath | null {
    const lastSlash = this.value.lastIndexOf("/");
    if (lastSlash < 0) {
      return null;
    }
    return NotePath.create(this.value.slice(0, lastSlash));
  }

  toString(): string {
    return this.value;
  }
}
