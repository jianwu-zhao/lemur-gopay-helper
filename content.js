(() => {
  const S = self.GoPayLongLinkShared;
  if (!S) return;

  const bodyText = document.body ? document.body.innerText : '';
  if (!S.isInteresting(location.href, bodyText)) return;

  const items = S.parseAll(location.href, bodyText).slice(0, 8);
  if (!items.length) return;

  let autoHandled = false;

  async function getSettings() {
    try {
      const saved = await chrome.storage.local.get(S.DEFAULT_SETTINGS);
      return { ...S.DEFAULT_SETTINGS, ...saved };
    } catch (_) {
      return S.DEFAULT_SETTINGS;
    }
  }

  function showToast(text) {
    const toast = document.createElement('div');
    toast.textContent = text;
    toast.style.cssText = [
      'position:fixed',
      'left:50%',
      'bottom:24px',
      'transform:translateX(-50%)',
      'z-index:2147483647',
      'background:#020617',
      'color:#e2e8f0',
      'border:1px solid #334155',
      'border-radius:999px',
      'padding:8px 12px',
      'font-size:12px',
      'box-shadow:0 10px 30px rgba(0,0,0,.35)'
    ].join(';');
    document.documentElement.appendChild(toast);
    setTimeout(() => toast.remove(), 1600);
  }

  async function handleAuto() {
    if (autoHandled) return;
    autoHandled = true;

    const settings = await getSettings();
    const picked = S.pickBest(items, settings);
    if (!picked) return;

    if (settings.autoCopy) {
      try {
        await navigator.clipboard.writeText(picked.value);
        showToast('GoPay 链接已自动复制');
      } catch (_) {}
    }

    if (settings.autoOpen) {
      chrome.runtime.sendMessage({ type: 'OPEN_LINK', url: picked.value });
    }
  }

  const root = document.createElement('div');
  root.style.cssText = [
    'position:fixed',
    'right:12px',
    'bottom:12px',
    'z-index:2147483647',
    'width:300px',
    'max-height:50vh',
    'overflow:auto',
    'background:#0f172a',
    'color:#e2e8f0',
    'border:1px solid #334155',
    'border-radius:12px',
    'box-shadow:0 10px 30px rgba(0,0,0,.35)',
    'padding:10px'
  ].join(';');

  const title = document.createElement('div');
  title.textContent = 'GoPay 长链助手';
  title.style.cssText = 'font-size:13px;font-weight:700;margin-bottom:8px;';
  root.appendChild(title);

  items.forEach(item => {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'margin-bottom:8px;padding:8px;background:#111827;border-radius:10px;';
    const meta = document.createElement('div');
    meta.textContent = item.type;
    meta.style.cssText = 'font-size:11px;color:#93c5fd;margin-bottom:4px;';
    const text = document.createElement('div');
    text.textContent = item.value;
    text.style.cssText = 'font-size:12px;word-break:break-all;line-height:1.4;';
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:6px;margin-top:6px;';
    const copy = document.createElement('button');
    copy.textContent = '复制';
    copy.style.cssText = 'border:0;background:#2563eb;color:#fff;padding:6px 8px;border-radius:8px;font-size:12px;';
    copy.onclick = async () => {
      await navigator.clipboard.writeText(item.value);
      copy.textContent = '已复制';
      setTimeout(() => copy.textContent = '复制', 1000);
    };
    const open = document.createElement('button');
    open.textContent = '打开';
    open.style.cssText = 'border:0;background:#16a34a;color:#fff;padding:6px 8px;border-radius:8px;font-size:12px;';
    open.onclick = () => chrome.runtime.sendMessage({ type: 'OPEN_LINK', url: item.value });
    row.append(copy, open);
    wrap.append(meta, text, row);
    root.appendChild(wrap);
  });

  const close = document.createElement('button');
  close.textContent = '关闭';
  close.style.cssText = 'border:0;background:#334155;color:#fff;padding:6px 8px;border-radius:8px;font-size:12px;width:100%;';
  close.onclick = () => root.remove();
  root.appendChild(close);

  document.documentElement.appendChild(root);
  handleAuto();
})();
