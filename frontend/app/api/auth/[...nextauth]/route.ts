import { handlers } from "@/lib/auth";

/**
 * Auth.js API route handler.
 * Handles all /api/auth/* requests:
 *   GET  /api/auth/session
 *   POST /api/auth/signin
 *   POST /api/auth/signout
 *   GET  /api/auth/csrf
 *   GET  /api/auth/providers
 *   etc.
 */
export const { GET, POST } = handlers;
