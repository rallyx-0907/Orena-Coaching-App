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
export function focusRegion(element) {
  if (!element) return;
  element.setAttribute('tabindex', '-1');
  element.focus({ preventScroll: true });
}
let dialogSequence = 0;
export function dialog({ title, body, onReady }) {
  const opener = document.activeElement;
  const element = document.createElement('dialog');
  element.className = 'sheet';
  const titleId = `orena-sheet-title-${++dialogSequence}`;
  element.setAttribute('aria-labelledby', titleId);
  // The close control speaks the interface language the shell recorded, not
  // two languages at once.
  const closeLabel = document.documentElement.dataset.close || 'Close';
  element.innerHTML = `<form method="dialog"><button class="close" aria-label="${esc(closeLabel)}">×</button></form><h2 id="${titleId}">${esc(title)}</h2>${body}`;
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
/* Ask the shell for its working height before moving the learner to their
   work on a narrow screen, so the destination clears the header it will have.
   An event rather than an import: html.js sits below every room and must not
   know the shell. */
export function focusWork() {
  document.dispatchEvent(new CustomEvent('orena:work'));
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
