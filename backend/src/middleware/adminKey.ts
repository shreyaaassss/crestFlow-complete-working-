/**
 * Admin Key Middleware
 *
 * Protects internal analytics endpoints from public access.
 * Requires the X-Admin-Key header to match ADMIN_API_KEY env var.
 */
import { Request, Response, NextFunction } from "express";

const ADMIN_KEY = process.env.ADMIN_API_KEY ?? "";

export function requireAdminKey(req: Request, res: Response, next: NextFunction): void {
  const key = req.headers["x-admin-key"] as string | undefined;
  if (!ADMIN_KEY || key !== ADMIN_KEY) {
    res.status(403).json({ error: "Forbidden" });
    return;
  }
  next();
}
