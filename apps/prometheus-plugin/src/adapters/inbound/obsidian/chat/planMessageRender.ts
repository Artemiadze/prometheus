import type { ChatMessage } from "../../../../domain/entities/ChatMessage";

export function messageRenderKey(message: ChatMessage): string {
  const suffix =
    message.kind === "assistant" ? `:${message.insufficientContext}:${message.sources.length}` : "";
  return `${message.id}:${message.state}${suffix}`;
}

/** Message keys that need a DOM re-render compared to the previous snapshot. */
export function planMessageRender(
  prevKeys: readonly string[],
  messages: readonly ChatMessage[],
): readonly string[] {
  const nextKeys = messages.map(messageRenderKey);
  const changed: string[] = [];
  for (let index = 0; index < nextKeys.length; index += 1) {
    if (prevKeys[index] !== nextKeys[index]) {
      const key = nextKeys[index];
      if (key) {
        changed.push(key);
      }
    }
  }
  return changed;
}
