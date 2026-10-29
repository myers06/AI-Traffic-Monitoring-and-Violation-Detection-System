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
export const getDatabaseViolations = () =>
  request("/api/database-violations");
export const recognizePhoto = (file) => {
  const formData = new FormData();
  formData.append("file", file);

  return request("/api/recognize-photo", {
    method: "POST",
    body: formData,
  });
};

export const getVideos = () => request("/api/videos");

export const getPlates = (video) =>
  request("/api/plates" + (video ? `?video=${encodeURIComponent(video)}` : ""));

export const videoUrl = (path) => `/api/video?path=${encodeURIComponent(path)}`;

// XHR instead of fetch so we can report upload progress for large videos.
export const uploadVideo = (file, onProgress) =>
  new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);

    xhr.open("POST", "/api/videos/upload?analyze=true");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };
    xhr.onload = () => {
      let body = {};
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* not JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else reject(new Error(body.detail || xhr.statusText || "Upload failed"));
    };
    xhr.onerror = () => reject(new Error("Upload failed. Check the server is running."));
    xhr.send(form);
  });
