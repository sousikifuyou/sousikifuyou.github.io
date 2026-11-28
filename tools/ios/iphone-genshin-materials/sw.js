/* 原神素材ビュー：アイコン画像のキャッシュ用サービスワーカー
 *
 * 画像配信サーバー（Project Amber / Enka.Network）のアイコンだけを対象に、
 * 一度読み込んだ画像をブラウザの Cache Storage に保存し、次回からは通信せずに表示する。
 * アプリ本体（HTML）やデータ（genshin-data.json）は対象外（常に最新を読み込むため）。
 *
 * 保存する／しないはアプリの「画像を保存」設定に従う。サービスワーカーは localStorage を読めないため、
 * アプリが Cache Storage の "icon-settings" に設定値（on/off）を書き、ここで読む。
 * キャッシュの削除はアプリ側（保存しない設定にしたとき等）で caches.delete() する。
 */
const CACHE = "icons-v3";
const SETTINGS = "icon-settings";
const FLAG_URL = "/__icon-cache-enabled";

async function cacheEnabled() {
  try {
    const res = await (await caches.open(SETTINGS)).match(FLAG_URL);
    return !!res && (await res.text()) === "on";
  } catch { return false; }
}
const ICON_HOSTS = ["gi.yatta.moe", "enka.network"];

// 保存前に表示サイズに合わせて縮小・圧縮する（画面上の最大表示サイズ × 約3倍：高精細画面でもぼやけない大きさ）
//   キャラのアイコン（UI_AvatarIcon_*）: 最大 52px 表示 → 160px
//   素材・武器のアイコン               : 最大 30px 表示 → 96px
// 形式は透過を保てる WebP（作れないブラウザでは PNG）。元より大きくなる場合は元画像のまま。
async function shrink(res, url) {
  if (res.type === "opaque" || !res.ok) return res;          // 中身を読めない形式は縮小できない
  if (typeof OffscreenCanvas === "undefined" || typeof createImageBitmap !== "function") return res;
  try {
    const src = await res.clone().blob();
    const bmp = await createImageBitmap(src);
    const max = /UI_AvatarIcon/.test(url) ? 160 : 96;
    const scale = Math.min(1, max / Math.max(bmp.width, bmp.height));
    if (scale >= 1) { bmp.close?.(); return res; }
    const w = Math.round(bmp.width * scale), h = Math.round(bmp.height * scale);
    const canvas = new OffscreenCanvas(w, h);
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = "high";
    ctx.drawImage(bmp, 0, 0, w, h); bmp.close?.();
    let out = await canvas.convertToBlob({ type: "image/webp", quality: 0.85 });
    if (out.type !== "image/webp") out = await canvas.convertToBlob({ type: "image/png" });
    if (out.size >= src.size) return res;
    return new Response(out, { headers: { "content-type": out.type, "content-length": String(out.size) } });
  } catch { return res; }
}

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  let url;
  try { url = new URL(req.url); } catch { return; }
  if (!ICON_HOSTS.includes(url.hostname)) return;

  e.respondWith((async () => {
    if (!(await cacheEnabled())) return fetch(req);   // 保存しない設定 → 通常どおり読み込む
    const cache = await caches.open(CACHE);
    const hit = await cache.match(req.url);
    if (hit) return hit;                       // 保存済み → 通信しない
    // まず CORS で取得（配信サーバーが許可していれば、成否とサイズが分かる形式で保存できる）。
    // 許可されていなければ、<img> と同じ形式（opaque：中身・成否が見えない）で取得する。
    // opaque で読み込みに失敗した画像は、アプリ側がキャッシュから削除する。
    let res;
    try { res = await fetch(req.url, { mode: "cors", credentials: "omit" }); }
    catch { res = await fetch(req); }
    // 表示は元画像ですぐに行い、縮小・保存は裏で行う（初回表示を遅らせない）
    if (res.ok || res.type === "opaque") {
      const copy = res.clone();
      e.waitUntil(shrink(copy, req.url).then((small) => cache.put(req.url, small)).catch(() => {}));
    }
    return res;
  })());
});
