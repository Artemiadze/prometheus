import { InvalidIdentifierError } from "../errors";

const VAULT_ID = /^[a-z0-9][a-z0-9-]{5,63}$/;

/**
 * A stable, path-segment-safe Vault identifier.
 * Mirrors runtime VaultId (vault_id.py).
 */
export class VaultId {
  readonly value: string;

  private constructor(value: string) {
    this.value = value;
  }

  static create(value: string): VaultId {
    if (!VAULT_ID.test(value)) {
      throw new InvalidIdentifierError();
    }
    return new VaultId(value);
  }

  toString(): string {
    return this.value;
  }
}
