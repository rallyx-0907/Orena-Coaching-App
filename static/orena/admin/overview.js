/* Overview: what an operator needs to know on arrival, in the first screen -
   who is learning, who is new, what is published, and what needs action - and
   then the trends behind those numbers. Every figure comes from
   /api/admin/console/overview; anything that endpoint cannot compute is shown
   as unavailable, never as zero. */
import { barList, bindCharts, columnChart } from './charts.js';
import { chip, esc, fill, info, kv, languageName, num, panel, relative, table, dateTime, notice } from './format.js';
import { emptyBlock, errorBlock, failureDetail, loadingBlock, unavailableBlock } from './states.js';

export function subjectLabel(item, t, providerNames = {}) {
  const subject = item.subject ? t[`cap_${item.subject}`] || item.subject : '';
  const provider = item.provider ? providerNames[item.provider] || item.provider : '';
  return { subject, provider };
}

export function attentionItem(item, t, ui, sectionHref, providerNames = {}) {
  const names = subjectLabel(item, t, providerNames);
  const title = t[`attention_${item.kind}`] || item.kind;
  const detail = fill(t[`attention_${item.kind}_detail`] || '', {
    subject: names.subject,
    provider: names.provider,
    count: num(item.count, ui),
  });
  const section = t[`section_${item.section}`] || item.section;
  return `<li class="ac-attention__item" data-severity="${esc(item.severity)}">${chip(item.severity === 'critical' ? 'critical' : item.severity === 'warning' ? 'warning' : 'info', t, { label: t[`severity_${item.severity}`] })}<div><strong>${esc(title)}</strong><p>${esc(detail)}</p></div><a class="ac-link" href="${esc(sectionHref(item.section, item.link || {}))}">${esc(fill(t.attentionOpen, { section }))}</a></li>`;
}

function kpi({ label, value, sub, hintText = '', kind = '' }) {
  return `<div class="ac-kpi"${kind ? ` data-tone="${kind}"` : ''}><span class="ac-kpi__label">${esc(label)}${hintText ? info(hintText, label) : ''}</span><strong class="ac-kpi__value">${esc(value)}</strong><span class="ac-kpi__sub">${esc(sub)}</span></div>`;
}

/* Where each problem is acted on, down to the filter that shows it. */
/* The design's list is labelled "sorted by severity", so it is sorted here
   rather than trusting whatever order the endpoint happened to build. Equal
   severities keep the server's order, which is its own judgement of urgency. */
const SEVERITY_ORDER = { critical: 0, warning: 1, info: 2 };

export function bySeverity(items) {
  return [...(items || [])]
    .map((item, index) => ({ item, index }))
    .sort((a, b) => {
      const left = SEVERITY_ORDER[a.item.severity] ?? 3;
      const right = SEVERITY_ORDER[b.item.severity] ?? 3;
      return left - right || a.index - b.index;
    })
    .map((entry) => entry.item);
}

export function attentionLink(item) {
  if (item.kind === 'transcript_missing') return { kind: 'media', status: 'issues' };
  if (item.kind === 'content_waiting') return { kind: 'vocabulary', status: 'draft' };
  if (item.kind === 'import_failed') return { status: 'failed' };
  return {};
}

export function overviewView(data, t, ui, sectionHref) {
  const accounts = data.accounts || {};
  const activity = data.activity || {};
  const content = data.content || {};
  const imports = data.imports || {};
  const ai = data.ai || {};
  const attention = data.attention || [];
  const providerNames = ai.provider_names || {};
  const critical = attention.filter((item) => item.severity === 'critical').length;
  const peopleKnown = accounts.available && activity.available;

  const strip = `<div class="ac-kpis">${[
    kpi({
      label: t.kpiActive,
      value: activity.available ? num(activity.active_7d, ui) : '—',
      sub: activity.available ? fill(t.kpiActiveSub, { value: num(activity.active_30d, ui) }) : t.notAvailable,
      hintText: t.activeHint,
    }),
    kpi({
      label: t.kpiNew,
      value: accounts.available ? num(accounts.new_7d, ui) : '—',
      sub: accounts.available ? fill(t.kpiNewSub, { value: num(accounts.new_30d, ui), total: num(accounts.total, ui) }) : t.notAvailable,
    }),
    kpi({
      label: t.kpiReturning,
      value: activity.available ? num(activity.returning_7d, ui) : '—',
      sub: activity.available ? fill(t.kpiReturningSub, { new: num(activity.new_7d, ui) }) : t.notAvailable,
      hintText: t.returningHint,
    }),
    kpi({
      label: t.kpiContent,
      value: num(content.published, ui),
      sub: fill(t.kpiContentSub, {
        books: num(content.book?.published, ui),
        media: num(content.media?.published, ui),
        vocabulary: num(content.vocabulary?.published, ui),
      }),
    }),
    kpi({
      label: t.kpiAttention,
      value: num(attention.length, ui),
      sub: attention.length ? fill(t.kpiAttentionSub, { critical: num(critical, ui) }) : t.kpiAttentionNone,
      kind: critical ? 'bad' : attention.length ? 'warn' : 'ok',
    }),
  ].join('')}</div>`;

  const attentionPanel = panel({
    title: t.attentionTitle,
    className: 'ac-panel--attention',
    note: attention.length ? t.attentionSorted : '',
    body: attention.length
      ? `<ul class="ac-attention">${bySeverity(attention).map((item) => attentionItem({ ...item, link: attentionLink(item) }, t, ui, sectionHref, providerNames)).join('')}</ul>`
      : emptyBlock(t, { title: t.attentionEmpty, note: t.attentionEmptyNote }),
  });

  const health = Object.entries(ai.health || {}).filter(([, count]) => count > 0);
  const aiPanel = panel({
    title: t.aiPanelTitle,
    actions: `<a class="ac-link" href="${esc(sectionHref('ai'))}">${esc(fill(t.attentionOpen, { section: t.section_ai }))}</a>`,
    body: kv([
      [t.aiRuntime, chip(ai.runtime_mode === 'capability' ? 'capability' : ai.runtime_mode === 'legacy' ? 'legacy' : 'invalid', t)],
      [t.aiRoutes, esc(fill(t.aiRoutesValue, {
        configured: num(ai.capabilities?.configured, ui),
        configurable: num(ai.capabilities?.configurable, ui),
        enabled: num(ai.capabilities?.enabled, ui),
      }))],
      [t.aiProviders, esc(fill(t.aiProvidersValue, { configured: num(ai.providers?.configured, ui), total: num(ai.providers?.total, ui) }))],
      [t.aiHealth, health.length
        ? `<span class="ac-chips">${health.map(([state, count]) => chip(state, t, { label: `${t[`status_${state}`] || state} ${num(count, ui)}` })).join('')}</span>`
        : esc(t.aiHealthNone)],
    ]),
  });

  const trends = peopleKnown
    ? `<div class="ac-grid ac-grid--2">${panel({
        body: columnChart({
          title: t.chartRegistrations,
          series: (accounts.registrations || []).map((point) => ({ date: point.date, value: point.count })),
          t,
          ui,
        }),
      })}${panel({
        body: columnChart({
          // Fourteen days, the window the design shows: long enough to read a
          // trend, short enough that every bar is legible.
          title: t.chartActive14,
          series: (activity.daily || []).slice(-14).map((point) => ({ date: point.date, value: point.learners })),
          t,
          ui,
        }),
      })}</div>`
    : `<div class="ac-grid ac-grid--2">${panel({
        title: t.chartRegistrations,
        body: unavailableBlock(t, { title: t.chartRegistrations, note: t.accountsUnavailable }),
      })}${panel({
        title: t.chartActive14,
        body: unavailableBlock(t, { title: t.chartActive14, note: t.accountsUnavailable }),
      })}</div>`;

  /* Every card the Overview promises stays on the board whether its number is
     a number, a zero, or nothing at all. A card that vanishes when its source
     is down changes the shape of the dashboard exactly when an operator is
     trying to work out what is wrong with it - and a hole in a row is the one
     thing they cannot read. The card stays and says which of the three it is. */
  const domains = panel({
    title: t.chartDomains,
    body: activity.available
      ? barList({
          ui,
          rows: (activity.domains || []).map((row) => ({
            label: t[`domain_${row.domain}`] || row.domain,
            value: row.events,
            note: fill(t.domainLearners, { count: num(row.learners, ui) }),
          })),
        })
      : unavailableBlock(t, { title: t.chartDomains, note: t.activityUnavailable }),
  });

  const languages = panel({
    title: t.chartLanguages,
    body: data.languages?.available
      ? table({
          head: [t.colLanguage, { label: t.languagesProfiles, numeric: true }, { label: t.languagesActive, numeric: true }],
          rows: languageRows(data.languages, t, ui),
          empty: t.notAvailable,
        })
      : unavailableBlock(t, { title: t.chartLanguages, note: t.languagesUnavailable }),
  });

  const sources = content.sources || {};
  const unavailableSources = Object.entries(sources).filter(([, state]) => state !== 'ok');
  /* By skill, published against waiting - the two numbers an operator decides
     with. Reading keeps its own lifecycle and its own endpoint, so its row is
     absent rather than zero when that endpoint cannot answer. */
  const readingCounts = data.reading || null;
  const skillRows = [
    ['book', content.book?.published, content.book?.archived, t.contentWaitingArchived],
    ['media', content.media?.published, content.media?.transcript_missing, t.contentWaitingTranscript],
    ['vocabulary', content.vocabulary?.published, content.vocabulary?.draft, t.contentWaitingDraft],
    readingCounts
      ? ['reading', readingCounts.published, readingCounts.needs_review, t.contentWaitingReview]
      : null,
  ].filter(Boolean);
  const contentPanel = panel({
    title: t.contentPanel,
    actions: `<a class="ac-link" href="${esc(sectionHref('content'))}">${esc(fill(t.attentionOpen, { section: t.section_content }))}</a>`,
    body: `${table({
      head: [t.colSkill, { label: t.colPublished, numeric: true }, { label: t.colWaiting, numeric: true }, t.colWaitingMeans],
      rows: skillRows.map(([kind, published, waiting, meaning]) => [
        esc(t[`kind_${kind}`] || kind),
        esc(num(published ?? 0, ui)),
        esc(num(waiting ?? 0, ui)),
        esc(meaning),
      ]),
      empty: t.notAvailable,
    })}${readingCounts ? '' : unavailableBlock(t, { title: t.kind_reading, note: t.readingOpsUnavailable })}${kv([
      [t.lastImport, imports.available ? esc(imports.last_import_at ? relative(imports.last_import_at, ui) : t.none) : esc(t.notAvailable)],
      [t.failedImports7d, imports.available ? esc(num(imports.failed_7d, ui)) : esc(t.notAvailable)],
    ])}${unavailableSources.length ? `<p class="ac-chips">${unavailableSources.map(([kind]) => chip('unavailable', t, { label: t[`sourceUnavailable_${kind}`] || kind })).join('')}</p>` : ''}`,
  });

  /* System health: the readiness the server already computes, as a panel with
     a check an operator can run - the design's "Kiểm tra". Nothing here probes
     a provider; it re-reads the evidence. */
  const readiness = data.readiness || null;
  const healthPanel = panel({
    title: t.systemHealthTitle,
    actions: `<button type="button" class="ac-button" data-ac-recheck>${esc(t.systemHealthCheck)}</button>`,
    body: readiness && readiness.available !== false
      ? `${kv([
          [t.overall, chip(readiness.state, t)],
          [t.evidence, chip(readiness.evidence_state, t)],
          [t.approval, chip(readiness.approval_state || 'not_granted', t)],
        ])}${table({
          head: [t.colIndicator, t.colState, t.colSourceOps],
          rows: (readiness.indicators || []).slice(0, 6).map((indicator) => [
            esc(t[`indicator_${indicator.name}`] || indicator.name),
            chip(indicator.state, t),
            esc(indicator.source || '—'),
          ]),
          empty: t.notAvailable,
        })}`
      : unavailableBlock(t, { title: t.systemHealthTitle, note: t.readinessUnavailableNote }),
  });

  return `${strip}<div class="ac-grid ac-grid--attention">${attentionPanel}${aiPanel}</div>${trends}<div class="ac-grid ac-grid--2">${contentPanel}${healthPanel}</div><div class="ac-grid ac-grid--2">${domains}${languages}</div><p class="ac-footnote">${esc(fill(t.generatedAt, { time: dateTime(data.generated_at, ui) }))}</p>`;
}

function languageRows(languages, t, ui) {
  const profiles = new Map((languages.profiles || []).map((row) => [row.language, row.learners]));
  const active = new Map((languages.active_30d || []).map((row) => [row.language, row.learners]));
  const codes = [...new Set([...profiles.keys(), ...active.keys()])].sort();
  return codes.map((code) => [esc(languageName(code, t)), esc(num(profiles.get(code) || 0, ui)), esc(num(active.get(code) || 0, ui))]);
}

export async function renderOverview(container, env) {
  const { t, ui, api, alive } = env;

  const load = async () => {
    container.innerHTML = loadingBlock(t, { shape: 'cards', rows: 4 });
    /* Three reads, none of which may take the section down with it: the
       overview is the answer, readiness and Reading are panels that say
       "unavailable" on their own if they cannot answer. */
    const [overview, readiness, reading] = await Promise.allSettled([
      api.overview(),
      api.readiness(),
      api.readingOperations(),
    ]);
    if (!alive()) return;
    if (overview.status === 'rejected') {
      const failure = failureDetail(overview.reason, t);
      container.innerHTML = errorBlock(t, {
        title: t.stateErrorTitle,
        detail: failure.detail,
        reference: failure.reference,
        link: `<a class="ac-link" href="${esc(env.href('operations'))}">${esc(t.stateSeeOperations)}</a>`,
      });
      container.querySelector('[data-ac-retry]')?.addEventListener('click', load, { once: true });
      return;
    }
    const data = {
      ...overview.value,
      readiness: readiness.status === 'fulfilled' ? readiness.value : null,
      reading: reading.status === 'fulfilled' ? reading.value.articles || {} : null,
    };
    if (data.reading) data.reading.published = reading.value.published ?? data.reading.published ?? 0;
    env.remember?.({ attention: data.attention || [] });
    container.innerHTML = overviewView(data, t, ui, env.href);
    bindCharts(container, { ui });
    container.querySelector('[data-ac-recheck]')?.addEventListener('click', load);
  };

  await load();
}
