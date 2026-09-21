import type { Notifier } from "../../src/application/ports/Notifier";

export type NotifierRecord = {
  readonly level: "info" | "warning" | "error";
  readonly message: string;
};

export class FakeNotifier implements Notifier {
  readonly records: NotifierRecord[] = [];

  info(message: string): void {
    this.records.push({ level: "info", message });
  }

  warning(message: string): void {
    this.records.push({ level: "warning", message });
  }

  error(message: string): void {
    this.records.push({ level: "error", message });
  }
}
