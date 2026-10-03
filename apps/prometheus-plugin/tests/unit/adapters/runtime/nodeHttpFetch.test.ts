import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { afterEach, describe, expect, it } from "vitest";

import { nodeHttpFetch } from "../../../../src/adapters/outbound/runtime/nodeHttpFetch";

type Received = { method: string; contentLength: string | undefined; body: string };

let server: Server | undefined;

async function listen(received: Received[]): Promise<string> {
  server = createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk: Buffer) => chunks.push(chunk));
    req.on("end", () => {
      received.push({
        method: req.method ?? "",
        contentLength: req.headers["content-length"],
        body: Buffer.concat(chunks).toString("utf8"),
      });
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end("{}");
    });
  });
  await new Promise<void>((resolve) => server?.listen(0, "127.0.0.1", resolve));
  return `http://127.0.0.1:${(server?.address() as AddressInfo).port}`;
}

afterEach(async () => {
  await new Promise<void>((resolve) => (server ? server.close(() => resolve()) : resolve()));
  server = undefined;
});

describe("nodeHttpFetch request body", () => {
  it("sends a UTF-8 JSON body byte-for-byte", async () => {
    const received: Received[] = [];
    const base = await listen(received);
    const body = JSON.stringify({ query: "Что такое Docker" });

    const response = await nodeHttpFetch(`${base}/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });

    expect(response.status).toBe(200);
    expect(received).toHaveLength(1);
    expect(received[0]?.body).toBe(body);
    expect(received[0]?.contentLength).toBe(String(Buffer.byteLength(body, "utf8")));
  });

  it("sends no body for GET", async () => {
    const received: Received[] = [];
    const base = await listen(received);

    await nodeHttpFetch(`${base}/v1/health`);

    expect(received[0]?.body).toBe("");
  });
});
