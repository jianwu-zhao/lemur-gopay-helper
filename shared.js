(() => {
  const KEYWORDS = [
    'gopay', 'gopaylink', 'golink', 'pay', 'checkout', 'redirect', 'deeplink', 'deep_link'
  ];

  const PARAM_CANDIDATES = [
    'url', 'link', 'target', 'target_url', 'targetUrl', 'redirect', 'redirect_url', 'redirectUrl',
    'return_url', 'returnUrl', 'goto', 'go', 'openurl', 'open_url', 'deeplink', 'deep_link',
    'dl', 'longurl', 'long_url', 'scheme', 'q', 'qr', 'qr_url', 'qrUrl'
  ];

  const DEFAULT_SETTINGS = {
    autoCopy: false,
    autoOpen: false,
    preferDeepLink: true,
    pickMode: 'best',
  };

  function safeDecode(value) {
    let current = String(value || '');
    for (let i = 0; i < 4; i += 1) {
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

  function looksLikeUrl(str) {
    return /^(https?:\/\/|gopay:\/\/|gojek:\/\/|intent:\/\/)/i.test(String(str || '').trim());
  }

  function isDeepLink(str) {
    return /^(gopay:\/\/|gojek:\/\/|intent:\/\/)/i.test(String(str || '').trim());
  }

  function uniqByValue(arr) {
    const seen = new Set();
    return arr.filter(item => {
      const key = `${item.type}::${item.value}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function collectHttpLinks(str, source = 'raw') {
    const out = [];
    const text = String(str || '');
    const regex = /(https?:\/\/[^\s'"<>\]\)]+|gopay:\/\/[^\s'"<>\]\)]+|gojek:\/\/[^\s'"<>\]\)]+|intent:\/\/[^\s'"<>\]\)]+)/ig;
    let match;
    while ((match = regex.exec(text))) {
      out.push({ type: source, value: safeDecode(match[1]) });
    }
    return out;
  }

  function parseUrl(url) {
    const results = [];
    const decodedUrl = safeDecode(url);
    results.push(...collectHttpLinks(decodedUrl, 'self'));

    try {
      const u = new URL(decodedUrl);
      for (const [key, value] of u.searchParams.entries()) {
        const lower = key.toLowerCase();
        const decoded = safeDecode(value);
        if (PARAM_CANDIDATES.includes(lower) || looksLikeUrl(decoded) || /https?:\/\//i.test(decoded)) {
          results.push({ type: `param:${key}`, value: decoded });
          results.push(...collectHttpLinks(decoded, `nested:${key}`));
        }
      }
    } catch (_) {}

    return uniqByValue(results).filter(x => x.value && x.value.length > 6);
  }

  function parseText(text) {
    const rawLinks = collectHttpLinks(safeDecode(text), 'text');
    const nested = rawLinks.flatMap(item => parseUrl(item.value));
    return uniqByValue([...rawLinks, ...nested]);
  }

  function parseAll(currentUrl, bodyText = '') {
    return uniqByValue([
      ...parseUrl(currentUrl),
      ...parseText(bodyText || '')
    ]);
  }

  function isInteresting(url, text = '') {
    const sample = `${url || ''}\n${String(text || '').slice(0, 3000)}`.toLowerCase();
    return KEYWORDS.some(k => sample.includes(k));
  }

  function pickBest(items, settings = DEFAULT_SETTINGS) {
    const list = Array.isArray(items) ? items.filter(Boolean) : [];
    if (!list.length) return null;

    const deep = list.filter(x => isDeepLink(x.value));
    const http = list.filter(x => /^https?:\/\//i.test(String(x.value || '')));

    if (settings.pickMode === 'last') return list[list.length - 1] || null;
    if (settings.pickMode === 'deep') return deep[0] || list[0] || null;
    if (settings.pickMode === 'http') return http[0] || list[0] || null;
    if (settings.preferDeepLink) return deep[0] || http[0] || list[0] || null;
    return http[0] || deep[0] || list[0] || null;
  }

  self.GoPayLongLinkShared = {
    KEYWORDS,
    PARAM_CANDIDATES,
    DEFAULT_SETTINGS,
    safeDecode,
    looksLikeUrl,
    isDeepLink,
    uniqByValue,
    collectHttpLinks,
    parseUrl,
    parseText,
    parseAll,
    isInteresting,
    pickBest,
  };
})();
