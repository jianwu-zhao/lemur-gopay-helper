const DEFAULT_SETTINGS = {
  autoCopy: false,
  autoOpen: false,
  preferDeepLink: true,
  pickMode: 'best',
};

async function getCurrentTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

async function loadSettings() {
  const saved = await chrome.storage.local.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...saved };
}

async function saveSettings(settings) {
  await chrome.storage.local.set(settings);
}

function bindSettings(settings) {
  const autoCopy = document.getElementById('autoCopy');
  const autoOpen = document.getElementById('autoOpen');
  const preferDeepLink = document.getElementById('preferDeepLink');
  const pickMode = document.getElementById('pickMode');

  autoCopy.checked = settings.autoCopy;
  autoOpen.checked = settings.autoOpen;
  preferDeepLink.checked = settings.preferDeepLink;
  pickMode.value = settings.pickMode;

  [autoCopy, autoOpen, preferDeepLink, pickMode].forEach(el => {
    el.addEventListener('change', async () => {
      await saveSettings({
        autoCopy: autoCopy.checked,
        autoOpen: autoOpen.checked,
        preferDeepLink: preferDeepLink.checked,
        pickMode: pickMode.value,
      });
    });
  });
}

function render(items) {
  const app = document.getElementById('app');
  if (!items.length) {
    app.className = 'empty';
    app.textContent = '没有找到可解析的 GoPay 长链。你可以先打开目标页面，再点插件按钮。';
    return;
  }

  app.className = '';
  app.innerHTML = '';

  items.forEach(item => {
    const box = document.createElement('div');
    box.className = 'item';
    box.innerHTML = `
      <div class="tag">${item.type}</div>
      <div class="url"></div>
      <div class="actions">
        <button class="copy">复制</button>
        <button class="open">打开</button>
      </div>
    `;
    box.querySelector('.url').textContent = item.value;
    box.querySelector('.copy').addEventListener('click', async () => {
      await navigator.clipboard.writeText(item.value);
      box.querySelector('.copy').textContent = '已复制';
      setTimeout(() => box.querySelector('.copy').textContent = '复制', 1000);
    });
    box.querySelector('.open').addEventListener('click', async () => {
      chrome.runtime.sendMessage({ type: 'OPEN_LINK', url: item.value });
    });
    app.appendChild(box);
  });
}

(async () => {
  const settings = await loadSettings();
  bindSettings(settings);

  const tab = await getCurrentTab();
  const [{ result } = {}] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => {
      const bodyText = document.body ? document.body.innerText : '';
      return {
        href: location.href,
        bodyText,
      };
    }
  });

  const parsed = self.GoPayLongLinkShared.parseAll(result?.href || tab.url || '', result?.bodyText || '');
  render(parsed);
})();
