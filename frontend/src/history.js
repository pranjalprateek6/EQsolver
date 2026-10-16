// Recently solved equations, kept only in this browser. Storage can be
// unavailable (private windows, blocked site data), so every access is
// guarded and the app works the same without it.
const KEY = "eqsolver.history";
const MAX_ITEMS = 8;

export function loadHistory() {
  try {
    const items = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(items) ? items.filter((i) => typeof i?.expression === "string") : [];
  } catch {
    return [];
  }
}

// Put an expression at the front (moving it if already there) and return the
// new list.
export function remember(expression, history = loadHistory()) {
  const trimmed = expression.trim();
  if (!trimmed) return history;
  const next = [{ expression: trimmed }, ...history.filter((i) => i.expression !== trimmed)].slice(
    0,
    MAX_ITEMS
  );
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // not persisted, but still shown for this visit
  }
  return next;
}

export function clearHistory() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // nothing stored to clear
  }
  return [];
}

// A link that opens the app with this equation solved. Only the equation
// goes in the link (in the fragment, so it is never sent to the server).
export function shareLink(expression) {
  const url = new URL(window.location.href);
  url.search = "";
  url.hash = `q=${encodeURIComponent(expression)}`;
  return url.toString();
}

export function expressionFromLink() {
  const match = window.location.hash.match(/^#q=(.*)$/);
  if (!match) return "";
  try {
    return decodeURIComponent(match[1]).slice(0, 300);
  } catch {
    return "";
  }
}
