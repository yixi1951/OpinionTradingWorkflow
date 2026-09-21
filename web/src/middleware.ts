import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const COOKIE = "ot_dashboard_auth";

export function middleware(request: NextRequest) {
  const password = process.env.DASHBOARD_PASSWORD?.trim();
  if (!password) {
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;
  if (
    pathname.startsWith("/login") ||
    pathname.startsWith("/api/auth") ||
    pathname.startsWith("/_next")
  ) {
    return NextResponse.next();
  }

  const token = request.cookies.get(COOKIE)?.value;
  if (token === password) {
    return NextResponse.next();
  }

  const login = new URL("/login", request.url);
  login.searchParams.set("from", pathname);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
