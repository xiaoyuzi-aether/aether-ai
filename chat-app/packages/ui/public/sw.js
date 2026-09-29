/* 清理旧版 Service Worker 与其缓存（一次性自毁脚本）
 * 旧版 AETHER 页面注册过 Service Worker，会把旧页面钉在浏览器缓存里。
 * 本文件覆盖旧 sw.js：安装即激活，激活时清空所有缓存并注销自身，
 * 让站点恢复走网络、加载最新版本。之后不再有 SW 控制本站点。
 */
self.addEventListener('install', function () {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    (async function () {
      try {
        const keys = await caches.keys();
        await Promise.all(keys.map(function (k) { return caches.delete(k); }));
      } catch (e) { /* 忽略 */ }
      try {
        await self.registration.unregister();
      } catch (e) { /* 忽略 */ }
      try {
        const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
        clients.forEach(function (c) {
          try { c.navigate(c.url); } catch (e) { /* 忽略 */ }
        });
      } catch (e) { /* 忽略 */ }
    })()
  );
});

/* 不拦截任何请求：所有请求直接走网络 */
self.addEventListener('fetch', function () {});
