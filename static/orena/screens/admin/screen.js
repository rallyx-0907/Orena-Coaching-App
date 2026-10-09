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
  overview: (routeId) => (routeId === 'adminTraffic'
    ? import('./traffic.js').then((module) => module.mountTraffic)
    : import('./control.js').then((module) => module.mountControl)),
  users: (routeId) => (routeId === 'adminPlans'
    ? import('./plans.js').then((module) => module.mountPlans)
    : routeId === 'adminFeedback'
      ? import('./feedback.js').then((module) => module.mountFeedback)
      : import('./control.js').then((module) => module.mountControl)),
  operations: () => import('./control.js').then((module) => module.mountControl),
  ai: (routeId) => (routeId === 'adminAiCosts'
    ? import('./costs.js').then((module) => module.mountCosts)
    : import('./ai.js').then((module) => module.mountAi)),
  content: (routeId) => (READING_ROUTES.has(routeId)
    ? import('./reading.js').then((module) => module.mountReading)
    : GRAMMAR_ROUTES.has(routeId)
      ? import('./grammar.js').then((module) => module.mountGrammar)
      : import('./content.js').then((module) => module.mountContent)),
  imports: () => import('./imports.js').then((module) => module.mountImports),
};
const GRAMMAR_ROUTES = new Set(['adminGrammar', 'adminGrammarPoint']);
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
