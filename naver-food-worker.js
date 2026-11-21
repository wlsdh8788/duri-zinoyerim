/**
 * Optional live NAVER API HUB local-search proxy for GitHub Pages.
 * Deploy to Cloudflare Workers, then set NAVER_API_CLIENT_ID and
 * NAVER_API_CLIENT_SECRET using Worker secrets. Never expose them in HTML/JS.
 */
const ALLOWED_ORIGIN = "https://wlsdh8788.github.io";
function cors(origin) {
  return {
    "Access-Control-Allow-Origin": origin === ALLOWED_ORIGIN ? origin : ALLOWED_ORIGIN,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
    "Cache-Control": "no-store"
  };
}
function json(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json; charset=utf-8", ...cors(origin) }
  });
}
export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(origin) });
    }
    if (request.method !== "GET") return json({ error: "Method not allowed" }, 405, origin);
    if (origin && origin !== ALLOWED_ORIGIN) return json({ error: "Origin forbidden" }, 403, origin);
    const input = new URL(request.url);
    if (input.pathname !== "/search") return json({ error: "Not found" }, 404, origin);
    const query = (input.searchParams.get("q") || "").trim();
    if (query.length < 2 || query.length > 80 || /[<>\r\n]/.test(query)) {
      return json({ error: "검색어는 2~80자로 입력" }, 400, origin);
    }
    if (!env.NAVER_API_CLIENT_ID || !env.NAVER_API_CLIENT_SECRET) {
      return json({ error: "NAVER API HUB 키 미설정" }, 503, origin);
    }
    const apiUrl = new URL("https://naverapihub.apigw.ntruss.com/search/v1/local");
    apiUrl.searchParams.set("query", "강릉 " + query);
    apiUrl.searchParams.set("display", "5");
    apiUrl.searchParams.set("start", "1");
    apiUrl.searchParams.set("sort", "comment");
    apiUrl.searchParams.set("format", "json");
    try {
      const response = await fetch(apiUrl, {
        headers: {
          "X-NCP-APIGW-API-KEY-ID": env.NAVER_API_CLIENT_ID,
          "X-NCP-APIGW-API-KEY": env.NAVER_API_CLIENT_SECRET
        }
      });
      if (!response.ok) return json({ error: "NAVER API error", code: response.status }, 502, origin);
      const data = await response.json();
      // Do not cache/republish results; only return this request's live results.
      const items = (data.items || []).filter(x =>
        (x.roadAddress || x.address || "").includes("강릉시")
      ).map(x => ({
        name: String(x.title || "").replace(/<[^>]*>/g, ""),
        category: x.category || "",
        address: x.roadAddress || x.address || ""
      }));
      return json({ source: "NAVER API HUB", items, total: items.length }, 200, origin);
    } catch {
      return json({ error: "Upstream unavailable" }, 502, origin);
    }
  }
};
