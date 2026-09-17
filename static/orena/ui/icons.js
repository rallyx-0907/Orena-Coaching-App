const strokes = {
  compass: '<circle cx="12" cy="12" r="9"/><path d="m16 8-3 5-5 3 3-5Z"/>',
  return: '<path d="M4 10a8 8 0 1 1 2 8M4 4v6h6M12 7v5l3 2"/>',
  book: '<path d="M12 5v15M12 5C9 3 5 3 2 4v15c3-1 7-1 10 1 3-2 7-2 10-1V4c-3-1-7-1-10 1Z"/>',
  sound: '<path d="M3 10v4m4-8v12m5-16v20m5-17v14m4-9v4"/>',
  focus: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/><circle cx="12" cy="12" r="3"/>',
  pen: '<path d="m4 16 12-12 4 4L8 20H4Zm9-9 4 4M3 23h18"/>',
  voice: '<path d="M8 14h-3V3h16v11h-8l-5 4ZM3 9H1v13h12v-4"/>',
  spark: '<path d="m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3Z"/>',
  folder: '<path d="M2 6V3h7l3 3h10v15H2Z"/>',
  leaf: '<path d="M4 20C-2 6 10 4 21 3c-1 12-4 19-17 17Zm0 0L16 8"/>',
};

export function entryIcon(name) {
  return `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${strokes[name] || strokes.compass}</svg>`;
}
