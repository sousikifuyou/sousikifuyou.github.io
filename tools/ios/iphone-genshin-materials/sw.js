/* 原神素材ビュー：アイコン画像のキャッシュ用サービスワーカー
 *
 * 画像配信サーバー（Project Amber / Enka.Network）のアイコンだけを対象に、
 * 一度読み込んだ画像をブラウザの Cache Storage に保存し、次回からは通信せずに表示する。
 * アプリ本体（HTML）やデータ（genshin-data.json）は対象外（常に最新を読み込むため）。
 *
 * キャッシュの削除はアプリ側（アイコン表示を「表示しない」にしたとき）で caches.delete() する。
 */
const CACHE = "icons-v1";
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
