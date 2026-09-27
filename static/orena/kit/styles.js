/* A screen's own stylesheet, loaded the first time the screen is entered (the shell and kit
   sheets are in the page from the start). Resolves when the sheet has applied, so a screen can
   await it before it paints and never flashes unstyled. */
const loaded = new Map();

export function useStyles(path) {
  if (loaded.has(path)) return loaded.get(path);
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = `/orena-assets/${path}`;
  const ready = new Promise((resolve) => {
    link.addEventListener('load', () => resolve(true), { once: true });
    link.addEventListener('error', () => resolve(false), { once: true });
  });
  document.head.append(link);
  loaded.set(path, ready);
  return ready;
}
