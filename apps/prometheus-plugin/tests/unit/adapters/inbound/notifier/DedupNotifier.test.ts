import { describe, expect, it } from "vitest";

import { DedupNotifier } from "../../../../../src/adapters/inbound/notifier/DedupNotifier";
import { FakeClock } from "../../../../fakes/FakeClock";
import { FakeNotifier } from "../../../../fakes/FakeNotifier";

describe("DedupNotifier", () => {
  it("suppresses identical messages within the window", () => {
    const inner = new FakeNotifier();
    const clock = new FakeClock(new Date(0));
    const notifier = new DedupNotifier(inner, clock, { windowMs: 30_000 });

    notifier.error("Boom");
    notifier.error("Boom");
    notifier.error("Boom");
    expect(inner.records).toHaveLength(1);
    expect(inner.records[0]?.message).toBe("Boom");
  });

  it("re-emits after the window with a repeat count", () => {
    const inner = new FakeNotifier();
    const clock = new FakeClock(new Date(0));
    const notifier = new DedupNotifier(inner, clock, { windowMs: 30_000 });

    notifier.warning("Sync failed");
    notifier.warning("Sync failed");
    notifier.warning("Sync failed");
    clock.advance(30_000);
    notifier.warning("Sync failed");

    expect(inner.records).toHaveLength(2);
    expect(inner.records[1]?.message).toBe("Sync failed (repeated 2 times)");
  });

  it("does not dedupe different messages or levels", () => {
    const inner = new FakeNotifier();
    const clock = new FakeClock(new Date(0));
    const notifier = new DedupNotifier(inner, clock);

    notifier.error("A");
    notifier.warning("A");
    notifier.error("B");
    expect(inner.records).toHaveLength(3);
  });
});
