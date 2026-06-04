chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== 'OPEN_LINK') return;

  const url = String(message.url || '').trim();
  if (!url) {
    sendResponse({ ok: false, error: 'empty url' });
    return true;
  }

  chrome.tabs.create({ url }, () => {
    const err = chrome.runtime.lastError;
    if (err) {
      sendResponse({ ok: false, error: err.message });
    } else {
      sendResponse({ ok: true });
    }
  });

  return true;
});
