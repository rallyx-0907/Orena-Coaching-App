/* Small charts for the admin console.

   Two forms only, because the console only has two chart jobs: a count per day
   (a single-series column chart) and a few magnitudes by category (labelled
   horizontal bars). One series means one mark colour and no legend - the title
   names what is plotted. Marks wear the accent token, text wears text tokens,
   gridlines are solid hairlines, and every chart carries its numbers as a
   table as well, so a value is never reachable only by hovering.

   Built from HTML boxes rather than a scaled SVG so that axis text keeps its
   real size at every width: a viewBox shrinks its labels with the chart. */
import { esc, fill, num, dateShort } from './format.js';

export function niceCeiling(value) {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((factor) => factor * power >= value) || 10;
  return Math.max(1, step * power);
}

/* `series` is [{date, value}] oldest first, one entry per day. */
export function columnChart({ title, series = [], t, ui, empty = '' }) {
  const values = series.map((point) => Math.max(0, Number(point.value) || 0));
  const max = Math.max(0, ...values);
  const top = niceCeiling(max);
  const ticks = [0, top / 2, top].filter((tick, index, all) => Number.isInteger(tick) && all.indexOf(tick) === index);
  const peakIndex = max > 0 ? values.lastIndexOf(max) : -1;
  const summary = max > 0
    ? fill(t.chartPeak, { value: num(max, ui), date: dateShort(series[peakIndex].date, ui) })
    : empty || t.chartEmpty;
  const scale = ticks
    .map((tick) => `<span style="bottom:${(tick / top) * 100}%">${esc(num(tick, ui))}</span>`)
    .join('');
  const grid = ticks
    .map((tick) => `<span class="ac-chart__gridline" style="bottom:${(tick / top) * 100}%"></span>`)
    .join('');
  const columns = series
    .map((point, index) => {
      const value = values[index];
      const height = (value / top) * 100;
      return `<span class="ac-chart__column" data-index="${index}" data-date="${esc(point.date)}" data-value="${value}" title="${esc(`${dateShort(point.date, ui)}: ${num(value, ui)}`)}">${value > 0 ? `<span class="ac-chart__bar" style="height:${height}%">${index === peakIndex ? `<span class="ac-chart__peak">${esc(num(value, ui))}</span>` : ''}</span>` : ''}</span>`;
    })
    .join('');
  const labelIndexes = series.length ? [...new Set([0, Math.floor((series.length - 1) / 2), series.length - 1])] : [];
  const dates = labelIndexes
    .map((index) => `<span style="--at:${series.length > 1 ? index / (series.length - 1) : 0}">${esc(dateShort(series[index].date, ui))}</span>`)
    .join('');
  const rows = series
    .map((point, index) => `<tr><td>${esc(dateShort(point.date, ui))}</td><td data-numeric>${esc(num(values[index], ui))}</td></tr>`)
    .join('');
  return `<figure class="ac-chart" data-chart><figcaption><span class="ac-chart__title">${esc(title)}</span><span class="ac-chart__summary">${esc(summary)}</span></figcaption><div class="ac-chart__plot"><div class="ac-chart__scale" aria-hidden="true">${scale}</div><div class="ac-chart__area" role="img" aria-label="${esc(`${title}. ${summary}`)}" tabindex="0"><div class="ac-chart__grid" aria-hidden="true">${grid}</div><div class="ac-chart__columns" style="--count:${Math.max(1, series.length)}" aria-hidden="true">${columns}</div><div class="ac-chart__tooltip" hidden></div></div><div class="ac-chart__dates" aria-hidden="true">${dates}</div></div><details class="ac-chart__data"><summary>${esc(t.showData)}</summary><table class="ac-table ac-table--compact"><thead><tr><th scope="col">${esc(t.colDate)}</th><th scope="col" data-numeric>${esc(t.colValue)}</th></tr></thead><tbody>${rows}</tbody></table></details></figure>`;
}

/* `rows` are [{label, value, note}]; bars are scaled to the largest value. */
export function barList({ rows = [], ui, empty = '' }) {
  const max = Math.max(0, ...rows.map((row) => Number(row.value) || 0));
  if (!rows.length) return empty ? `<p class="ac-empty">${esc(empty)}</p>` : '';
  return `<ul class="ac-bars">${rows
    .map((row) => {
      const value = Number(row.value) || 0;
      const width = max > 0 ? Math.max(value > 0 ? 2 : 0, Math.round((value / max) * 100)) : 0;
      return `<li><span class="ac-bars__label">${esc(row.label)}${row.note ? `<small>${esc(row.note)}</small>` : ''}</span><span class="ac-bars__track" aria-hidden="true"><span class="ac-bars__fill" style="width:${width}%"></span></span><span class="ac-bars__value">${esc(num(value, ui))}</span></li>`;
    })
    .join('')}</ul>`;
}

/* Hover and keyboard for every column chart inside `root`: the column under
   the pointer, or the one reached with the arrow keys, shows its date and
   value. The tooltip is filled with textContent - dates and numbers only. */
export function bindCharts(root, { ui } = {}) {
  root?.querySelectorAll?.('[data-chart]').forEach((figure) => {
    const area = figure.querySelector('.ac-chart__area');
    const tooltip = figure.querySelector('.ac-chart__tooltip');
    const columns = [...figure.querySelectorAll('.ac-chart__column')];
    if (!area || !tooltip || !columns.length) return;
    let active = -1;
    const show = (index) => {
      columns.forEach((column, position) => column.toggleAttribute('data-active', position === index));
      if (index < 0) {
        tooltip.hidden = true;
        return;
      }
      const column = columns[index];
      tooltip.textContent = '';
      const value = document.createElement('strong');
      value.textContent = num(column.dataset.value, ui);
      const date = document.createElement('span');
      date.textContent = dateShort(column.dataset.date, ui);
      tooltip.append(value, date);
      tooltip.hidden = false;
      const box = area.getBoundingClientRect();
      const hit = column.getBoundingClientRect();
      const centre = hit.left - box.left + hit.width / 2;
      tooltip.style.left = `${Math.min(Math.max(centre, 36), Math.max(36, box.width - 36))}px`;
    };
    columns.forEach((column, index) => {
      column.addEventListener('pointerenter', () => {
        active = index;
        show(index);
      });
    });
    area.addEventListener('pointerleave', () => {
      active = -1;
      show(-1);
    });
    area.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
        event.preventDefault();
        const step = event.key === 'ArrowRight' ? 1 : -1;
        active = active < 0 ? (step > 0 ? 0 : columns.length - 1) : Math.min(columns.length - 1, Math.max(0, active + step));
        show(active);
      } else if (event.key === 'Escape') {
        active = -1;
        show(-1);
      }
    });
    area.addEventListener('blur', () => show(-1));
  });
}
