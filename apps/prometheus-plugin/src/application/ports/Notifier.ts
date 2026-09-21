/**
 * User-facing notifications. Adapters map this to Obsidian Notice.
 */
export interface Notifier {
  info(message: string): void;
  warning(message: string): void;
  error(message: string): void;
}
