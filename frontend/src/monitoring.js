// Optional error tracking. Sentry is loaded only when the build sets
// VITE_SENTRY_DSN; without it nothing extra is downloaded and reportError is a
// no-op. Drawings and photos are sent to the API as base64 images, so request
// bodies are never attached and any image-like string is blanked before an
// event leaves the browser.

let sentry = null;

const IMAGE_LIKE = /^data:image\/|^[A-Za-z0-9+/_-]{2048,}={0,2}$/;

export function stripImages(value) {
  if (Array.isArray(value)) return value.map(stripImages);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([k, v]) => [k, k === "image" ? "[removed]" : stripImages(v)])
    );
  }
  if (typeof value === "string" && IMAGE_LIKE.test(value)) return "[removed]";
  return value;
}

export function scrubEvent(event) {
  if (event.request) {
    delete event.request.data;
    delete event.request.cookies;
  }
  delete event.user;
  return stripImages(event);
}

export async function initMonitoring() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;
  sentry = await import("./sentry");
  sentry.init({
    dsn,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || "production",
    // errors only: no tracing or session replay is set up
    sendDefaultPii: false,
    beforeSend: scrubEvent,
    beforeBreadcrumb: (crumb) => stripImages(crumb),
  });
}

export function reportError(error, extra) {
  sentry?.captureException(error, extra ? { extra: stripImages(extra) } : undefined);
}
