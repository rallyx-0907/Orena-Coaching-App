/* Polar's embedded checkout (PR-MON-9 §3.2, D-MON-033): Polar's own card form, opened as an overlay inside the app for
   a first purchase. Orena never sees card data - this module only opens Polar's frame and relays its four events.

   The script is Polar's published bundle at a pinned release, loaded once and only when a learner continues to
   payment. Truth sources never mix: an embed event says where Polar's payment is; access comes only from the
   subscription webhook, read back through the server. */

export const POLAR_EMBED_SRC = 'https://cdn.jsdelivr.net/npm/@polar-sh/checkout@0.4.3/dist/embed.global.js';

let loading = null;

export function loadPolarEmbed(doc = document) {
  if (doc.defaultView?.Polar?.EmbedCheckout) return Promise.resolve(doc.defaultView.Polar.EmbedCheckout);
  if (!loading) {
    loading = new Promise((resolve, reject) => {
      const script = doc.createElement('script');
      script.src = POLAR_EMBED_SRC;
      script.async = true;
      script.crossOrigin = 'anonymous';
      script.addEventListener('load', () => {
        const embed = doc.defaultView?.Polar?.EmbedCheckout;
        if (embed) resolve(embed);
        else reject(new Error('polar_embed_unavailable'));
      });
      script.addEventListener('error', () => {
        loading = null;
        reject(new Error('polar_embed_unavailable'));
      });
      doc.head.append(script);
    });
  }
  return loading;
}

/* The theme the app is showing: an explicit data-theme wins, otherwise the operating system's (D-089). */
export function appTheme(doc = document) {
  const declared = doc.documentElement.getAttribute('data-theme');
  if (declared === 'dark' || declared === 'light') return declared;
  return doc.defaultView?.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/* Open a checkout URL in Polar's embed. `on` receives `confirmed` (the payment is being processed), `success`
   (Polar accepted the payment; the embed is told not to navigate away), `close` (closed by the learner) and
   `error`. Returns a function that closes the embed. */
export async function openPolarCheckout(url, on = {}, doc = document) {
  const Embed = await loadPolarEmbed(doc);
  const checkout = await Embed.create(url, { theme: appTheme(doc) });
  checkout.addEventListener('confirmed', () => on.confirmed?.());
  checkout.addEventListener('success', (event) => {
    event.preventDefault(); // stay in the app: the sheet waits for the webhook, never Polar's redirect
    checkout.close();
    on.success?.();
  });
  checkout.addEventListener('close', () => on.close?.());
  return () => checkout.close();
}
