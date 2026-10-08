/* Markup for the new learner UI (D-091): tagged templates that escape by default.

   html`<p>${text}</p>` escapes every interpolated value unless it is itself a Markup (the result of
   another html`` or of raw()), so learner content and API data can never become markup by
   accident. Arrays are joined, null/undefined/false render nothing. The result is a Markup whose
   toString() is the HTML - hand it to mount() or to innerHTML. */

export class Markup {
  constructor(value) {
    this.value = value;
  }
  toString() {
    return this.value;
  }
}

const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };

export function esc(value = '') {
  return String(value).replace(/[&<>"']/g, (char) => ENTITIES[char]);
}

function part(value) {
  if (value == null || value === false) return '';
  if (value instanceof Markup) return value.value;
  if (Array.isArray(value)) return value.map(part).join('');
  return esc(value);
}

export function html(strings, ...values) {
  let out = strings[0];
  for (let i = 0; i < values.length; i += 1) out += part(values[i]) + strings[i + 1];
  return new Markup(out);
}

/* Trusted markup that is already safe: icon SVG from kit/icons.js, a brand <use>. Never learner or
   API text. */
export function raw(value) {
  return new Markup(String(value ?? ''));
}

/* class="a b" from a list with falsy entries dropped. */
export function cls(...names) {
  return names.flat().filter(Boolean).join(' ');
}

/* Replace an element's content with markup. */
export function mount(element, markup) {
  if (element) element.innerHTML = String(markup);
  return element;
}

/* An inline style value from a number of px or a string, for the few geometry values the design
   computes (a progress width, a ring dash). Never a colour: colours come from tokens. */
export function px(value) {
  return typeof value === 'number' ? `${value}px` : String(value);
}
