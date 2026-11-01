// Only public, non-secret values may be exposed to the browser.
// Production image: built with an EMPTY value, so requests go to /api on the same origin.
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
