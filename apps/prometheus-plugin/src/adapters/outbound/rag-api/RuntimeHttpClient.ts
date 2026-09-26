import packageMetadata from "../../../../package.json";

import type { RuntimeSessionRegistry } from "../../../application/services/RuntimeSessionRegistry";
import {
  isAbortError,
  isPrometheusPluginError,
  RuntimeContractError,
  RuntimeRequestTimeoutError,
  RuntimeSessionRequiredError,
  RuntimeUnavailableError,
} from "../../../domain/errors";
import { mapRuntimeApiError } from "./apiErrors";

export const PLUGIN_VERSION = packageMetadata.version;

export type RuntimeResponseDecoder<T> = (payload: unknown, requestId: string | null) => T;

export type RuntimeHttpClientOptions = {
  readonly sessions: RuntimeSessionRegistry;
  readonly getHealthBaseUrl: () => string;
  readonly fetchFn?: typeof fetch;
  readonly timeoutMs?: number;
  readonly pluginVersion?: string;
  readonly requestIdFactory?: () => string;
  readonly onUnauthorized?: () => void | Promise<void>;
};

export type RuntimeHttpRequest<T> = {
  readonly method?: "GET" | "POST" | "PUT" | "DELETE";
  readonly body?: unknown;
  readonly signal?: AbortSignal | undefined;
  readonly protected?: boolean;
  readonly decode: RuntimeResponseDecoder<T>;
};

const DEFAULT_TIMEOUT_MS = 15_000;

/**
 * Fetch transport for the loopback runtime API.
 * It owns timeout/cancellation, protected headers and versioned error envelopes.
 */
export class RuntimeHttpClient {
  private readonly fetchFn: typeof fetch;
  private readonly timeoutMs: number;
  private readonly pluginVersion: string;
  private readonly requestIdFactory: () => string;

  constructor(private readonly options: RuntimeHttpClientOptions) {
    this.fetchFn = options.fetchFn ?? fetch;
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.pluginVersion = options.pluginVersion ?? PLUGIN_VERSION;
    this.requestIdFactory = options.requestIdFactory ?? (() => crypto.randomUUID());
  }

  currentConnectionKey(): string | null {
    const session = this.options.sessions.get();
    return session ? `${session.connection.baseUrl}#${this.options.sessions.getRevision()}` : null;
  }

  async request<T>(path: string, request: RuntimeHttpRequest<T>): Promise<T> {
    const isProtected = request.protected ?? true;
    const session = this.options.sessions.get();
    if (isProtected && !session) {
      throw new RuntimeSessionRequiredError();
    }

    const baseUrl = session?.connection.baseUrl ?? this.options.getHealthBaseUrl();
    const url = buildRuntimeUrl(baseUrl, path);
    const requestId = isProtected ? this.requestIdFactory() : null;
    const headers = new Headers({ Accept: "application/json" });
    if (request.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    if (isProtected && session && requestId) {
      headers.set("Authorization", `Bearer ${session.connection.sessionToken}`);
      headers.set("X-Request-ID", requestId);
      headers.set("X-Prometheus-Plugin-Version", this.pluginVersion);
    }

    const controller = new AbortController();
    let timedOut = false;
    const onCallerAbort = (): void => {
      controller.abort();
    };
    if (request.signal?.aborted) {
      throw abortError();
    }
    request.signal?.addEventListener("abort", onCallerAbort, { once: true });
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, this.timeoutMs);

    try {
      const init: RequestInit = {
        method: request.method ?? "GET",
        headers,
        signal: controller.signal,
      };
      if (request.body !== undefined) {
        init.body = JSON.stringify(request.body);
      }
      const response = await this.fetchFn(url, init);
      const responseRequestId = response.headers.get("X-Request-ID");
      const payload = await readJson(response, responseRequestId);
      if (!response.ok) {
        const error = mapRuntimeApiError(payload, response.status, responseRequestId);
        if (response.status === 401) {
          this.options.sessions.clear();
          await safelyNotifyUnauthorized(this.options.onUnauthorized);
        }
        throw error;
      }
      return request.decode(payload, responseRequestId);
    } catch (error) {
      if (request.signal?.aborted) {
        throw abortError();
      }
      if (timedOut) {
        throw new RuntimeRequestTimeoutError(this.timeoutMs);
      }
      if (isPrometheusPluginError(error)) {
        throw error;
      }
      if (isAbortError(error)) {
        throw error;
      }
      throw new RuntimeUnavailableError();
    } finally {
      clearTimeout(timer);
      request.signal?.removeEventListener("abort", onCallerAbort);
    }
  }
}

async function readJson(response: Response, requestId: string | null): Promise<unknown> {
  const text = await response.text();
  if (text.length === 0) {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new RuntimeContractError(requestId);
  }
}

function buildRuntimeUrl(baseUrl: string, path: string): string {
  let parsed: URL;
  try {
    parsed = new URL(baseUrl);
  } catch {
    throw new RuntimeContractError();
  }
  const loopbackHosts = new Set(["127.0.0.1", "localhost", "[::1]"]);
  if (parsed.protocol !== "http:" || !loopbackHosts.has(parsed.hostname)) {
    throw new RuntimeContractError();
  }
  if (!path.startsWith("/") || path.includes("..")) {
    throw new RuntimeContractError();
  }
  const queryIndex = path.indexOf("?");
  const pathname = queryIndex >= 0 ? path.slice(0, queryIndex) : path;
  const search = queryIndex >= 0 ? path.slice(queryIndex) : "";
  const root = parsed.pathname.replace(/\/+$/, "").replace(/\/v1$/, "");
  parsed.pathname = `${root}/v1${pathname}`.replace(/\/{2,}/g, "/");
  parsed.search = search;
  parsed.hash = "";
  return parsed.toString();
}

async function safelyNotifyUnauthorized(
  listener: RuntimeHttpClientOptions["onUnauthorized"],
): Promise<void> {
  try {
    await listener?.();
  } catch {
    // The original typed 401 remains the observable failure.
  }
}

function abortError(): Error {
  return new DOMException("The operation was aborted", "AbortError");
}
