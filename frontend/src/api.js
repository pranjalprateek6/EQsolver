// In dev the API is on a separate port; in a production build the frontend is
// served by Flask itself, so calls go to the same origin (relative URLs).
export const API_URL =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.DEV ? "http://127.0.0.1:5000" : "");

// A sleeping free-tier server can take most of a minute to wake up, so give
// the first request plenty of time before calling it a failure.
const REQUEST_TIMEOUT_MS = 90_000;

const STATUS_MESSAGES = {
  413: "That image is too large. Try a smaller photo or crop it to the equation.",
  429: "Too many requests in a row. Wait a few seconds and try again.",
  502: "The server is restarting. Try again in a moment.",
  503: "The server is busy or restarting. Try again in a moment.",
  504: "The server took too long to answer. Try again in a moment.",
};

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

// POST JSON and return the parsed body. Always rejects with an ApiError whose
// message is safe to show the user, even when the server (or a proxy in front
// of it) answers with HTML instead of JSON.
export async function postJson(path, payload, { signal } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort);

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } catch (err) {
    if (signal?.aborted) throw new ApiError("Cancelled.", 0);
    if (controller.signal.aborted) {
      throw new ApiError("The server took too long to answer. Try again in a moment.", 0);
    }
    throw new ApiError("Could not reach the server. Check your connection and try again.", 0);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    // a proxy error page or an empty body; fall through to the status text
  }

  if (!response.ok) {
    const message =
      (data && data.error && capitalize(data.error)) ||
      STATUS_MESSAGES[response.status] ||
      `Something went wrong (error ${response.status}).`;
    throw new ApiError(withPeriod(message), response.status, data);
  }
  if (data === null) {
    throw new ApiError("The server sent an unreadable answer. Try again.", response.status);
  }
  return data;
}

function capitalize(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function withPeriod(text) {
  return /[.!?]$/.test(text) ? text : `${text}.`;
}
