/* Platform Admin at `#/admin`.

   The console itself lives in static/orena/admin/ - Overview, AI & Models,
   Users, Content, Imports and Operations over the existing admin contracts.
   This module stays the router's entry point, so app.js does not change: the
   route is still admin-only in the navigation and every call it makes is
   guarded on the server.

   The book, media and vocabulary importers that used to be stacked on this
   page are the Imports section now (admin/imports.js), sending the same
   requests to the same importers. */
import { renderConsole, noAccessView } from '../admin/shell.js';

export function renderAdmin(root, ctx) {
  /* Canonical study 08: someone who is not an administrator opening /admin
     gets a page that says so and offers the way back - not a console that
     loads and then fails six requests. The server refuses them either way;
     this is only what they are shown. */
  if (ctx?.user && ctx.user.is_admin === false) {
    root.innerHTML = noAccessView(ctx.ui);
    return () => {};
  }
  return renderConsole(root, ctx);
}
