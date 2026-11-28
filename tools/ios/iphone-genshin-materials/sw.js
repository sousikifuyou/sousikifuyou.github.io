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
const CACHE = "icons-v1";
const SETTINGS = "icon-settings";
const FLAG_URL = "/__icon-cache-enabled";

async function cacheEnabled() {
  try {
    const res = await (await caches.open(SETTINGS)).match(FLAG_URL);
    return !!res && (await res.text()) === "on";
  } catch { return false; }
}
const ICON_HOSTS = ["gi.yatta.moe", "enka.network"];

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
    const res = await fetch(req);
    // <img> の読み込みは中身を確認できない形式（opaque）で返るため、そのまま保存する。
    // 読み込みに失敗した画像は、アプリ側がキャッシュから削除する。
    if (res.ok || res.type === "opaque") {
      cache.put(req.url, res.clone()).catch(() => {});
    }
    return res;
  })());
});
