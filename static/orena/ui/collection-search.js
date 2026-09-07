import { esc } from './html.js';
// The result list owns its rows. This only supplies one accessible search and
// facet interaction, reusable for content and concept collections.
export function collectionSearch(c, { facet, options }) {
  return `<form class="collection-search" data-collection-search><label>${esc(c.searchCollection)}<input type="search" name="query" autocomplete="off"></label><label>${esc(facet)}<select name="facet"><option value="all">${esc(c.collectionAll)}</option>${options.map(({ value, label }) => `<option value="${esc(value)}">${esc(label)}</option>`).join('')}</select></label></form><p class="meta" role="status" data-collection-count></p>`;
}
export function bindCollectionSearch(root, c, render) {
  const form = root.querySelector('[data-collection-search]');
  if (!form) return;
  const update = () => {
    const count = render({
      query: form.elements.query.value,
      facet: form.elements.facet.value,
    });
    root.querySelector('[data-collection-count]').textContent =
      `${count} ${c.collectionResults}`;
  };
  form.onsubmit = (event) => {
    event.preventDefault();
    update();
  };
  form.oninput = update;
  update();
}
