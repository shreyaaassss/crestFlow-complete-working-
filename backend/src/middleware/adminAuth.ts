/**
 * Admin Auth Middleware — Supabase JWT Verification
 *
 * Protects internal admin endpoints (/platform/stats, /platform/config,
 * and admin-mode GET /orders).
 *
 * The admin frontend sends the Supabase session access_token as:
 *   Authorization: Bearer <supabase_access_token>
 *
 * This middleware verifies:
 *   1. The token is a valid Supabase JWT (signed with SUPABASE_JWT_SECRET)
 *   2. The token's email claim matches ADMIN_EMAIL env var
 */
import { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";

const SUPABASE_JWT_SECRET = process.env.SUPABASE_JWT_SECRET ?? "";
const ADMIN_EMAIL         = process.env.ADMIN_EMAIL ?? "";

interface SupabaseJwtPayload {
  sub?:   string;
  email?: string;
  role?:  string;
  exp?:   number;
}

export function requireAdminAuth(req: Request, res: Response, next: NextFunction): void {
  const header = req.headers.authorization ?? "";
  const token  = header.startsWith("Bearer ") ? header.slice(7) : "";

  if (!token) {
    res.status(401).json({ error: "Unauthorized: no session token provided" });
    return;
  }

  if (!SUPABASE_JWT_SECRET) {
    res.status(503).json({ error: "Server misconfigured: SUPABASE_JWT_SECRET not set" });
    return;
  }

  try {
    const payload = jwt.verify(token, SUPABASE_JWT_SECRET) as SupabaseJwtPayload;

    if (!ADMIN_EMAIL || payload.email !== ADMIN_EMAIL) {
      res.status(403).json({ error: "Forbidden: not an admin account" });
      return;
    }

    next();
  } catch (err: any) {
    if (err.name === "TokenExpiredError") {
      res.status(401).json({ error: "Unauthorized: session expired — please log in again" });
    } else {
      res.status(401).json({ error: "Unauthorized: invalid session token" });
    }
  }
}

/**
 * Non-blocking admin check — returns true/false without sending a response.
 * Used in GET /orders and GET /orders/:id to decide response shape.
 */
export function isAdminRequest(req: Request): boolean {
  try {
    const header = req.headers.authorization ?? "";
    const token  = header.startsWith("Bearer ") ? header.slice(7) : "";
    if (!token || !SUPABASE_JWT_SECRET || !ADMIN_EMAIL) return false;
    const payload = jwt.verify(token, SUPABASE_JWT_SECRET) as SupabaseJwtPayload;
    return payload.email === ADMIN_EMAIL;
  } catch {
    return false;
  }
}
