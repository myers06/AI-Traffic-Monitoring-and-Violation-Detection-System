async function request(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      msg = (await res.json()).detail || msg;
    } catch {
      /* body was not JSON */
    }
    throw new Error(msg);
  }
  return res.json();
}

export const getStats = () => request("/api/stats");
export const getStatus = () => request("/api/status");
export const getViolations = (type) =>
  request("/api/violations" + (type && type !== "all" ? `?type=${type}` : ""));

export const startAnalysis = (source) =>
  request("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source }),
  });

export const clearResults = () => request("/api/clear", { method: "POST" });