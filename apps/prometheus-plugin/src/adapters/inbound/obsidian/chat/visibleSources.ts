import type { AssistantChatMessage } from "../../../../domain/entities/ChatMessage";
import type { SourceReference } from "../../../../domain/entities/SourceReference";

export function visibleSources(message: AssistantChatMessage): readonly SourceReference[] {
  if (message.insufficientContext || message.state !== "complete") {
    return [];
  }
  return message.sources;
}
