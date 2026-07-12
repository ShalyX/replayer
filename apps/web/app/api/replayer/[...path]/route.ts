import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE;
  const apiKey = process.env.REPLAYER_API_KEY || process.env.NEXT_PUBLIC_API_KEY;
  if (!apiBase || !apiKey) {
    return NextResponse.json({ detail: "RepLayer server proxy is not configured" }, { status: 503 });
  }

  const { path } = await context.params;
  const target = new URL(`${apiBase.replace(/\/$/, "")}/${path.map(encodeURIComponent).join("/")}`);
  request.nextUrl.searchParams.forEach((value, key) => target.searchParams.append(key, value));

  try {
    const response = await fetch(target, {
      method: request.method,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
      cache: "no-store",
      headers: {
        "content-type": request.headers.get("content-type") || "application/json",
        "x-api-key": apiKey,
      },
    });
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") || "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "RepLayer hosted API is temporarily unreachable" }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
