import { request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import type { IncomingMessage, RequestOptions } from "node:http";
import { URL } from "node:url";

import type { FetchFn } from "./RuntimeDownloader";

/**
 * Node.js HTTP(S) fetch for runtime install/verify.
 * Obsidian's Chromium `fetch` cannot reliably reach loopback release mirrors (CORS / PNA).
 */
export const nodeHttpFetch: FetchFn = async (input, init = {}) => {
  const url = toUrl(input);
  const method = (init.method ?? "GET").toUpperCase();
  const headers = normalizeHeaders(init.headers);
  const signal = init.signal ?? undefined;

  const requestBody = toRequestBody(init.body);
  if (requestBody) {
    // Byte length, not string length: bodies routinely contain non-ASCII text.
    headers["content-length"] = String(requestBody.byteLength);
  }

  const payload = await requestBuffer(url, method, headers, signal, requestBody);
  return new Response(Uint8Array.from(payload.body), {
    status: payload.status,
    statusText: payload.statusText,
    headers: payload.headers,
  });
};

function toRequestBody(body: BodyInit | null | undefined): Buffer | undefined {
  if (body === null || body === undefined) {
    return undefined;
  }
  if (typeof body === "string") {
    return Buffer.from(body, "utf8");
  }
  if (body instanceof ArrayBuffer) {
    return Buffer.from(body);
  }
  if (ArrayBuffer.isView(body)) {
    return Buffer.from(body.buffer, body.byteOffset, body.byteLength);
  }
  throw new TypeError("Unsupported request body type for nodeHttpFetch");
}

function toUrl(input: RequestInfo | URL): URL {
  if (typeof input === "string") {
    return new URL(input);
  }
  if (input instanceof URL) {
    return input;
  }
  return new URL(input.url);
}

function normalizeHeaders(headers: HeadersInit | undefined): Record<string, string> {
  if (!headers) {
    return {};
  }
  if (headers instanceof Headers) {
    const out: Record<string, string> = {};
    headers.forEach((value, key) => {
      out[key] = value;
    });
    return out;
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return { ...headers };
}

type NodeResponse = {
  readonly status: number;
  readonly statusText: string;
  readonly headers: Headers;
  readonly body: Buffer;
};

function requestBuffer(
  url: URL,
  method: string,
  headers: Record<string, string>,
  signal: AbortSignal | undefined,
  body: Buffer | undefined,
  redirectLeft = 5,
): Promise<NodeResponse> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("The operation was aborted", "AbortError"));
      return;
    }

    const transport = url.protocol === "https:" ? httpsRequest : httpRequest;
    const options: RequestOptions = {
      protocol: url.protocol,
      hostname: url.hostname,
      port: url.port || undefined,
      path: `${url.pathname}${url.search}`,
      method,
      headers,
    };

    const req = transport(options, (res) => {
      void handleResponse(res).then(resolve, reject);
    });

    const onAbort = (): void => {
      req.destroy();
      reject(new DOMException("The operation was aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });

    req.on("error", (error) => {
      signal?.removeEventListener("abort", onAbort);
      reject(error);
    });
    req.end(body);

    async function handleResponse(res: IncomingMessage): Promise<NodeResponse> {
      signal?.removeEventListener("abort", onAbort);
      const status = res.statusCode ?? 0;
      const statusText = res.statusMessage ?? "";
      const location = res.headers.location;
      if (status >= 300 && status < 400 && location && redirectLeft > 0) {
        res.resume();
        const next = new URL(location, url);
        return requestBuffer(next, method, headers, signal, body, redirectLeft - 1);
      }

      const chunks: Buffer[] = [];
      for await (const chunk of res as AsyncIterable<Buffer | string>) {
        chunks.push(typeof chunk === "string" ? Buffer.from(chunk) : chunk);
      }
      const responseBody = Buffer.concat(chunks);
      const headerInit: Record<string, string> = {};
      for (const [key, value] of Object.entries(res.headers)) {
        if (typeof value === "string") {
          headerInit[key] = value;
        } else if (Array.isArray(value)) {
          headerInit[key] = value.join(", ");
        }
      }
      return {
        status,
        statusText,
        headers: new Headers(headerInit),
        body: responseBody,
      };
    }
  });
}
