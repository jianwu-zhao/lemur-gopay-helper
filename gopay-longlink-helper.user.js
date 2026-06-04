// ==UserScript==
// @name         GoPay LongLink Helper for Lemur
// @namespace    https://github.com/jianwu-zhao/lemur-gopay-helper
// @version      1.0.0
// @description  Parse GoPay/payment long links, decode nested redirect/deeplink URLs, copy or open them on mobile browsers.
// @author       pi
// @match        *://*/*
// @grant        GM_setClipboard
// @grant        GM_registerMenuCommand
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const KEYWORDS = ['gopay', 'gopaylink', 'golink', 'pay', 'checkout', 'redirect', 'deeplink', 'deep_link'];
  const PARAMS = [
    'url', 'link', 'target', 'target_url', 'targeturl', 'redirect', 'redirect_url', 'redirecturl',
    'return_url', 'returnurl', 'goto', 'go', 'openurl', 'open_url', 'deeplink', 'deep_link',
    'dl', 'longurl', 'long_url', 'scheme', 'q', 'qr', 'qr_url', 'qrurl'
  ];

  function safeDecode(value) {
    let current = String(value || '');
    for (let i = 0; i < 5; i += 1) {
      try {
        const next = decodeURIComponent(current.replace(/\+/g, '%20'));
        if (next === current) break;
        current = next;
      } catch (_) {
        break;
      }
    }
    return current;
  }

  function uniq(items) {
    const seen = new Set();
    return items.filter(item => {
      const key = item.value;
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function collectLinks(text, type) {
    const out = [];
    const raw = String(text || '');
    const re = /(https?:\/\/[^\s'"<>\]\)]+|gopay:\/\/[^\s'"<>\]\)]+|gojek:\/\/[^\s'"<>\]\)]+|intent:\/\/[^\s'"<>\]\)]+)/ig;
    let match;
    while ((match = re.exec(raw))) {
      out.push({ type, value: safeDecode(match[1]) });
    }
    return out;
  }

  function parseUrl(url) {
    const out = [];
    const decoded = safeDecode(url);
    out.push(...collectLinks(decoded, 'self'));
    try {
      const u = new URL(decoded);
      for (const [key, value] of u.searchParams.entries()) {
        const decodedValue = safeDecode(value);
        const lower = key.toLowerCase();
        if (PARAMS.includes(lower) || /^(https?:\/\/|gopay:\/\/|gojek:\/\/|intent:\/\/)/i.test(decodedValue)) {
          out.push({ type: 'param:' + key, value: decodedValue });
          out.push(...collectLinks(decodedValue, 'nested:' + key));
        }
      }
    } catch (_) {}
    return uniq(out);
  }

  function parseAll() {
    const bodyText = document.body ? document.body.innerText : '';
    const sample = (location.href + '\n' + bodyText.slice(0, 3000)).toLowerCase();
    if (!KEYWORDS.some(k => sample.includes(k))) return [];
    return uniq([
      ...parseUrl(location.href),
      ...collectLinks(safeDecode(bodyText), 'text'),
      ...collectLinks(document.documentElement.innerHTML, 'html')
    ]).slice(0, 20);
  }

  function copyText(text) {
    try {
      if (typeof GM_setClipboard === 'function') {
        GM_setClipboard(text, 'text');
        return true;
      }
    } catch (_) {}
    try {
      navigator.clipboard.writeText(text);
      return true;
    } catch (_) {}
    return false;
  }

  function buildPanel(items) {
    const old = document.getElementById('gopay-longlink-helper-panel');
    if (old) old.remove();

    const root = document.createElement('div');
    root.id = 'gopay-longlink-helper-panel';
    root.style.cssText = [
      'position:fixed', 'right:10px', 'bottom:10px', 'z-index:2147483647',
      'width:min(330px,calc(100vw - 20px))', 'max-height:55vh', 'overflow:auto',
      'background:#0f172a', 'color:#e2e8f0', 'border:1px solid #334155',
      'border-radius:12px', 'box-shadow:0 10px 30px rgba(0,0,0,.35)',
      'padding:10px', 'font-family:system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif'
    ].join(';');

    const title = document.createElement('div');
    title.textContent = 'GoPay 长链助手';
    title.style.cssText = 'font-size:14px;font-weight:700;margin-bottom:8px;';
    root.appendChild(title);

    if (!items.length) {
      const empty = document.createElement('div');
      empty.textContent = '没有找到可解析链接';
      empty.style.cssText = 'font-size:12px;color:#94a3b8;';
      root.appendChild(empty);
    }

    items.forEach(item => {
      const box = document.createElement('div');
      box.style.cssText = 'background:#111827;border-radius:10px;padding:8px;margin-bottom:8px;';

      const tag = document.createElement('div');
      tag.textContent = item.type;
      tag.style.cssText = 'font-size:11px;color:#93c5fd;margin-bottom:4px;';

      const text = document.createElement('div');
      text.textContent = item.value;
      text.style.cssText = 'font-size:12px;word-break:break-all;line-height:1.4;';

      const row = document.createElement('div');
      row.style.cssText = 'display:flex;gap:6px;margin-top:6px;';

      const copy = document.createElement('button');
      copy.textContent = '复制';
      copy.style.cssText = 'border:0;background:#2563eb;color:#fff;padding:6px 8px;border-radius:8px;font-size:12px;';
      copy.onclick = () => {
        copyText(item.value);
        copy.textContent = '已复制';
        setTimeout(() => copy.textContent = '复制', 1000);
      };

      const open = document.createElement('button');
      open.textContent = '打开';
      open.style.cssText = 'border:0;background:#16a34a;color:#fff;padding:6px 8px;border-radius:8px;font-size:12px;';
      open.onclick = () => window.open(item.value, '_blank');

      row.append(copy, open);
      box.append(tag, text, row);
      root.appendChild(box);
    });

    const close = document.createElement('button');
    close.textContent = '关闭';
    close.style.cssText = 'border:0;background:#334155;color:#fff;padding:7px 8px;border-radius:8px;font-size:12px;width:100%;';
    close.onclick = () => root.remove();
    root.appendChild(close);

    document.documentElement.appendChild(root);
  }

  function run() {
    buildPanel(parseAll());
  }

  if (typeof GM_registerMenuCommand === 'function') {
    GM_registerMenuCommand('打开 GoPay 长链助手', run);
  }

  setTimeout(() => {
    const items = parseAll();
    if (items.length) buildPanel(items);
  }, 800);
})();
