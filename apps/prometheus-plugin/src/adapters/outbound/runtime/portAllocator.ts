import { createServer } from "node:net";

const DEFAULT_MAX_ATTEMPTS = 5;

export async function allocateLoopbackPort(
  maxAttempts: number = DEFAULT_MAX_ATTEMPTS,
): Promise<number> {
  let lastError: Error | undefined;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      return await probeFreePort();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
    }
  }
  throw lastError ?? new Error("Failed to allocate a loopback port");
}

function probeFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.unref();
    server.on("error", (error) => {
      reject(error);
    });
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close(() => {
          reject(new Error("Unexpected server address"));
        });
        return;
      }
      const port = address.port;
      server.close((closeError) => {
        if (closeError) {
          reject(closeError);
          return;
        }
        resolve(port);
      });
    });
  });
}
