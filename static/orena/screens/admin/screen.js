/* Platform Admin in the new UI (D-101 E; Orena-Admin.dc.html): the host every #/admin/... place
   routes to. It decides access first - from what the shell already knows about the account, before a
   single admin request exists - and only then draws the Admin's own shell and the area's page.

   - not an admin: the design's No access frame, in place of the whole Admin; no admin request is made;
   - an admin: the shell (rail, header, phone chips) and the area's page. #/admin alone opens the first
     area of the control center (Overview).

   The server refuses non-admins on every admin route by itself (tests/test_admin_authorization_matrix.py);
   this is the client keeping its side, so a normal account never even asks. */
import { useStyles } from '../../kit/styles.js';
import { adminAccess, areaOf } from './model.js';
import { renderNoAccess } from './no-access.js';
import { drawAdminShell } from './frame.js';
import { mountTray } from './tray.js';

const AREA_PAGES = {
  overview: () => import('./control.js').then((module) => module.mountControl),
  users: () => import('./control.js').then((module) => module.mountControl),
  operations: () => import('./control.js').then((module) => module.mountControl),
  ai: () => import('./ai.js').then((module) => module.mountAi),
  content: (routeId) => (READING_ROUTES.has(routeId)
    ? import('./reading.js').then((module) => module.mountReading)
    : import('./content.js').then((module) => module.mountContent)),
  imports: () => import('./imports.js').then((module) => module.mountImports),
};
const READING_ROUTES = new Set(['adminReading', 'adminQueue', 'adminArticle', 'adminSet', 'adminAdd', 'adminSources', 'adminSource']);

export default async function admin(element, ctx) {
  await useStyles('screens/admin/admin.css');
  if (!ctx.isCurrent()) return undefined;
  const access = adminAccess(ctx.context);
  if (!access.allowed) {
    renderNoAccess(element, { email: access.email, name: access.name, backHref: ctx.href('today') });
    return undefined;
  }
  if (ctx.route.id === 'admin') {
    ctx.replace(ctx.href('adminOverview'));
    return undefined;
  }
  const area = areaOf(ctx.route.id);
  const load = AREA_PAGES[area];
  if (!load) {
    ctx.replace(ctx.href('adminAi'));
    return undefined;
  }
  const shell = drawAdminShell(element, { area, href: ctx.href, name: access.name });
  const leaveTray = mountTray(shell.tray, ctx.href);
  const mount = await load(ctx.route.id);
  if (!ctx.isCurrent()) {
    leaveTray();
    return undefined;
  }
  const leavePage = await mount(shell, ctx);
  return () => {
    leaveTray();
    if (typeof leavePage === 'function') leavePage();
  };
}
