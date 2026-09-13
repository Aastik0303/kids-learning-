import { checkHealth } from "@/services/api/client";

/**
 * Cross-cutting session concerns that do not belong to a single feature.
 *
 * The dev-only seed route that used to live here is gone. It unlocked and
 * completed a child's whole class in one call so the certificate could be
 * demonstrated, and a shipped app has no business being able to ask for that -
 * the server does not mount the route outside development either.
 */
export const sessionApi = {
  health: checkHealth,
};
