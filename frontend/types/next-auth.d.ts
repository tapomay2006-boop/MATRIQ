import { DefaultSession } from "next-auth";

// ─────────────────────────────────────────────
// Extend the built-in session and user types
// ─────────────────────────────────────────────
declare module "next-auth" {
  interface Session {
    sessionId?: string;
    sessionCreatedAt?: number;
    lastActiveAt?: number;
    error?: string;
    user: {
      id: string;
      role: string;
    } & DefaultSession["user"];
  }

  interface User {
    id?: string;
    role?: string;
    sessionId?: string;
  }
}

// ─────────────────────────────────────────────
// Extend the JWT type
// ─────────────────────────────────────────────
declare module "next-auth/jwt" {
  interface JWT {
    id?: string;
    role?: string;
    sessionId?: string;
    sessionCreatedAt?: number;
    lastActiveAt?: number;
    error?: string;
  }
}
