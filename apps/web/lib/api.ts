const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev-key";

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "content-type": "application/json",
      "x-api-key": API_KEY,
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    const message = await readableError(res);
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

async function readableError(res: Response): Promise<string> {
  const raw = await res.text();
  let message = raw;
  try {
    const parsed = JSON.parse(raw) as { detail?: string };
    message = parsed.detail || raw;
  } catch {
    message = raw;
  }
  return message
    .replace(/\u001b\[[0-9;?]*[A-Za-z]/g, "")
    .replace(/[?√âˆš]*\s*Enter password to decrypt keystore:\s*(?:\[hidden\]|\*|\s)*/gi, "")
    .replace(/Write Transaction Hash:\s*(0x[a-fA-F0-9]{64})/g, "Tx: $1")
    .replace(/Error:\s*UnknownRpcError:[\s\S]*/g, "GenLayer RPC timed out during readback.")
    .replace(/\*{2,}/g, "[hidden]")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 900);
}

export { API_BASE };
