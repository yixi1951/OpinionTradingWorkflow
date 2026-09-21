import { NextResponse } from "next/server";

const COOKIE = "ot_dashboard_auth";

export async function POST(request: Request) {
  const expected = process.env.DASHBOARD_PASSWORD?.trim();
  if (!expected) {
    return NextResponse.json({ ok: true, required: false });
  }

  let password = "";
  try {
    const body = await request.json();
    password = String(body?.password ?? "");
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid body" }, { status: 400 });
  }

  if (password !== expected) {
    return NextResponse.json({ ok: false, required: true }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true, required: true });
  res.cookies.set(COOKIE, expected, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return res;
}
