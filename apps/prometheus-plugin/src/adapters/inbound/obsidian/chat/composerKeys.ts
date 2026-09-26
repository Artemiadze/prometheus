export type ComposerKeyInput = {
  readonly key: string;
  readonly shiftKey: boolean;
  readonly isComposing?: boolean;
};

export type ComposerKeyAction = "send" | "newline" | "ignore";

export function resolveComposerKey(input: ComposerKeyInput): ComposerKeyAction {
  if (input.isComposing) {
    return "ignore";
  }
  if (input.key === "Enter") {
    return input.shiftKey ? "newline" : "send";
  }
  return "ignore";
}
