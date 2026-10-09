/* Platform Admin's No access frame (Orena-Admin.dc.html "No access"): a full-window page that says
   Admin access is required, who the account is and how to go back - and nothing about how access is
   decided. Drawn in place of the whole Admin, so a partial Admin is never exposed (brief §3), and
   drawn before any admin request exists. Used by the screen (a non-admin who reaches an admin
   address in the shell) and by main.js (a non-admin at an admin address). */
import { html, mount } from '../../kit/html.js';
import { brandChip } from '../../kit/brand.js';
import { t } from './copy.js';

export function noAccessMarkup({ email = '', name = '', backHref = '#/today' } = {}) {
  const who = String(email || name || '').trim();
  return html`<div class="a-noaccess" data-screen-label="No access"><div class="a-noaccess__card">
    ${brandChip({ size: 64, mark: 46, className: 'a-noaccess__mark' })}
    <h1 class="a-noaccess__title">${t('noAccessTitle')}</h1>
    <p class="a-noaccess__text">${who ? html`${t('noAccessBefore')}<b>${who}</b>${t('noAccessAfter')}` : t('noAccessAnon')}</p>
    <a class="a-btn a-btn--md a-btn--primary a-noaccess__back" href="${backHref}">${t('noAccessBack')}</a>
  </div></div>`;
}

export function renderNoAccess(target, info) {
  mount(target, noAccessMarkup(info));
}
