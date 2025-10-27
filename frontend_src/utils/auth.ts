export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function refreshAccessToken(refreshToken: string) {
  const res = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) throw new Error("Refresh failed");
  const data = await res.json();
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
  return data.access_token;
}

export async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const accessToken = localStorage.getItem("access_token");
  const refreshToken = localStorage.getItem("refresh_token");

  const headers = {
    ...options.headers,
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
  };

  let res = await fetch(`${API_URL}${url}`, { ...options, headers });
  if (res.status === 401 && refreshToken) {
    const newAccess = await refreshAccessToken(refreshToken);
    headers.Authorization = `Bearer ${newAccess}`;
    res = await fetch(`${API_URL}${url}`, { ...options, headers });
  }

  return res;
}
