import { describe, expect, it } from "vitest";

import {
  DiagnosticBuffer,
  maskArgvForDiagnostics,
} from "../../../../src/adapters/outbound/runtime/DiagnosticBuffer";

describe("DiagnosticBuffer", () => {
  it("masks session token in argv logs", () => {
    const masked = maskArgvForDiagnostics([
      "serve",
      "--session-token",
      "secret-token-value",
      "--port",
      "8765",
    ]);
    expect(masked).not.toContain("secret-token-value");
    expect(masked).toContain("***");
  });

  it("caps stored lines", () => {
    const buffer = new DiagnosticBuffer({ maxLines: 2 });
    buffer.append("stdout", "one\n");
    buffer.append("stdout", "two\n");
    buffer.append("stdout", "three\n");
    expect(buffer.snapshot()).toEqual(["[stdout] two", "[stdout] three"]);
  });
});
