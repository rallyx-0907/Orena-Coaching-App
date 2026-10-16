/* Two independent columns for the Admin page blocks (owner request 2026-10-16: no row-aligned
   gaps, configuration near the top).

   Pages author their blocks in one list, in the order a phone reads them (one column). On a desktop
   this module moves the blocks into two stacks inside the same `.a-blocks`: a block that says
   `data-col="left|right"` goes there, any other block goes to the shorter stack at that moment (so
   with no placement they alternate by height), and a full-width block (`.a-block--full`, metrics,
   banners ...) ends the run and the next run starts beneath it. Each block keeps its authored index
   in `data-ord`, so the phone layout (and a resize back) restores the authored order exactly.
   Tab and reader order follow the drawn order: the left stack top to bottom, then the right. */

const SPAN = '.a-block--full, .a-metrics, .a-banner, .a-skeleton, .a-loading, .a-error, .a-overview-metrics';

const isDesktop = () => document.documentElement.dataset.device !== 'mobile';

function restore(container) {
  const items = [...container.querySelectorAll('[data-ord]')].sort((a, b) => Number(a.dataset.ord) - Number(b.dataset.ord));
  container.replaceChildren(...items);
  delete container.dataset.cols;
}

function stacksFor(run, container, before) {
  const wrap = document.createElement('div');
  wrap.className = 'a-stacks';
  const left = document.createElement('div');
  const right = document.createElement('div');
  left.className = 'a-stack';
  right.className = 'a-stack';
  wrap.append(left, right);
  container.insertBefore(wrap, before);
  for (const item of run) {
    const want = item.dataset.col;
    let target = want === 'left' ? left : want === 'right' ? right : null;
    if (!target) target = right.offsetHeight < left.offsetHeight ? right : left;
    target.append(item);
  }
  return wrap;
}

function arrange(container) {
  const children = [...container.children];
  if (children.length < 2) { container.dataset.cols = 'one'; return; }
  const active = document.activeElement;
  const hadFocus = active && container.contains(active) ? active : null;
  const selection = hadFocus && typeof hadFocus.selectionStart === 'number' ? [hadFocus.selectionStart, hadFocus.selectionEnd] : null;
  children.forEach((child, index) => { child.dataset.ord = String(index); });
  let run = [];
  const flush = (before) => {
    if (run.length) stacksFor(run, container, before);
    run = [];
  };
  for (const child of children) {
    if (child.matches(SPAN)) { flush(child); continue; }
    run.push(child);
  }
  flush(null);
  container.dataset.cols = 'two';
  if (hadFocus && document.activeElement !== hadFocus) {
    hadFocus.focus({ preventScroll: true });
    if (selection && typeof hadFocus.setSelectionRange === 'function') hadFocus.setSelectionRange(selection[0], selection[1]);
  }
}

/* Arrange every block container under `page` for the current device. Safe to call repeatedly. */
export function layoutBlocks(page) {
  for (const container of page.querySelectorAll('.a-blocks:not(.a-blocks--one)')) {
    const state = container.dataset.cols;
    if (isDesktop()) {
      if (state === 'two' || state === 'one') continue;
      arrange(container);
    } else if (state === 'two') {
      restore(container);
    }
  }
}

/* Keep `page` arranged: after every repaint and when the device flips between phone and desktop.
   Invariant: a repaint replaces the page content through innerHTML (kit `mount`), which yields fresh,
   unarranged `.a-blocks`, so arrangement runs exactly once per paint and never on top of itself.
   Unplaced cards pick the shorter stack with the fonts available at that moment; once the fonts have
   loaded the page is re-balanced a single time, and only while nothing inside it has focus. */
export function watchBlocks(page) {
  if (typeof MutationObserver === 'undefined') return () => {};
  let queued = false;
  const run = () => { queued = false; layoutBlocks(page); };
  const observer = new MutationObserver(() => { if (!queued) { queued = true; queueMicrotask(run); } });
  observer.observe(page, { childList: true, subtree: true });
  const deviceWatch = new MutationObserver(() => layoutBlocks(page));
  deviceWatch.observe(document.documentElement, { attributes: true, attributeFilter: ['data-device'] });
  layoutBlocks(page);
  let live = true;
  document.fonts?.ready?.then(() => {
    if (!live) return;
    const focused = document.activeElement;
    if (focused && focused !== document.body && page.contains(focused)) return;
    for (const container of page.querySelectorAll('.a-blocks[data-cols="two"]')) {
      restore(container);
      arrange(container);
    }
  });
  return () => { live = false; observer.disconnect(); deviceWatch.disconnect(); };
}
