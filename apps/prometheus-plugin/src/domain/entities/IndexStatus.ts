export type IndexRecommendedAction = "reindex" | "wait" | "none";

export type IndexStatus =
  | { readonly kind: "notIndexed" }
  | { readonly kind: "indexing"; readonly progressPercent: number }
  | {
      readonly kind: "ready";
      readonly documentCount: number;
      readonly chunkCount: number;
      readonly lastIndexedAt: Date | null;
      readonly indexSizeBytes: number;
    }
  | { readonly kind: "reindexRequired"; readonly reason: string }
  | { readonly kind: "corrupted"; readonly reason: string };

export const IndexStatus = {
  notIndexed(): IndexStatus {
    return { kind: "notIndexed" };
  },
  indexing(progressPercent: number): IndexStatus {
    return { kind: "indexing", progressPercent };
  },
  ready(input: {
    documentCount: number;
    chunkCount: number;
    lastIndexedAt: Date | null;
    indexSizeBytes: number;
  }): IndexStatus {
    return { kind: "ready", ...input };
  },
  reindexRequired(reason: string): IndexStatus {
    return { kind: "reindexRequired", reason };
  },
  corrupted(reason: string): IndexStatus {
    return { kind: "corrupted", reason };
  },
};

export function recommendedActionForIndex(status: IndexStatus): IndexRecommendedAction {
  switch (status.kind) {
    case "notIndexed":
    case "reindexRequired":
    case "corrupted":
      return "reindex";
    case "indexing":
      return "wait";
    case "ready":
      return "none";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}
