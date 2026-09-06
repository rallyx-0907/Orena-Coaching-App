export function esc(value = '') {
  return String(value).replace(
    /[&<>"']/g,
    (char) =>
      ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;',
      })[char],
  );
}
export function safeExternal(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password
      ? url.href
      : '';
  } catch {
    return '';
  }
}
export function dialog({ title, body, onReady }) {
  const opener = document.activeElement;
  const element = document.createElement('dialog');
  element.className = 'sheet';
  element.setAttribute('aria-labelledby', 'sheetTitle');
  element.innerHTML = `<form method="dialog"><button class="close" aria-label="Close / 关闭">×</button></form><h2 id="sheetTitle">${esc(title)}</h2>${body}`;
  document.body.append(element);
  element.addEventListener(
    'close',
    () => {
      element.remove();
      if (opener?.isConnected) opener.focus();
    },
    { once: true },
  );
  element.showModal();
  onReady?.(element);
  return element;
}
let announcementTimer;
export function status(message) {
  const region = document.getElementById('announcement');
  clearTimeout(announcementTimer);
  if (region) {
    region.textContent = message;
    announcementTimer = setTimeout(() => {
      region.textContent = '';
    }, 7000);
  }
}
