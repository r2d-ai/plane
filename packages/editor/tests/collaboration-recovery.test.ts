import { describe, expect, test } from "vitest";

import { isForcedCloseCode, shouldAttemptHeal, STUCK_STAGE_MS } from "../src/core/helpers/collaboration-recovery";

const healInput = (overrides: Partial<Parameters<typeof shouldAttemptHeal>[0]> = {}) => ({
  isDisposed: false,
  stageKind: "synced" as const,
  isDocumentForceClosed: false,
  msSinceStageChange: 0,
  ...overrides,
});

describe("isForcedCloseCode", () => {
  test("treats only server document force-close codes as forced", () => {
    expect(isForcedCloseCode(4000)).toBe(true);
    expect(isForcedCloseCode(4001)).toBe(true);
    expect(isForcedCloseCode(4003)).toBe(true);
    expect(isForcedCloseCode(1006)).toBe(false);
    expect(isForcedCloseCode(4403)).toBe(false);
    expect(isForcedCloseCode(undefined)).toBe(false);
  });
});

describe("shouldAttemptHeal", () => {
  test("heals a terminal disconnected stage without user interaction", () => {
    expect(shouldAttemptHeal(healInput({ stageKind: "disconnected" }))).toBe(true);
  });

  test("never heals after disposal or a server-side document force close", () => {
    expect(shouldAttemptHeal(healInput({ stageKind: "disconnected", isDisposed: true }))).toBe(false);
    expect(shouldAttemptHeal(healInput({ stageKind: "disconnected", isDocumentForceClosed: true }))).toBe(false);
  });

  test("heals a connection stage only once it is wedged", () => {
    for (const stageKind of ["connecting", "reconnecting", "awaiting-sync"] as const) {
      expect(shouldAttemptHeal(healInput({ stageKind, msSinceStageChange: STUCK_STAGE_MS - 1 }))).toBe(false);
      expect(shouldAttemptHeal(healInput({ stageKind, msSinceStageChange: STUCK_STAGE_MS }))).toBe(true);
    }
  });

  test("leaves healthy and transient stages alone", () => {
    expect(shouldAttemptHeal(healInput({ stageKind: "synced", msSinceStageChange: STUCK_STAGE_MS * 10 }))).toBe(false);
    expect(shouldAttemptHeal(healInput({ stageKind: "initial", msSinceStageChange: STUCK_STAGE_MS * 10 }))).toBe(false);
  });
});
