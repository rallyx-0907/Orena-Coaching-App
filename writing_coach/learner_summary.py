"""LearnerSummary: what the learner's own evidence actually shows (I6, read step).

Specification: docs/product/ORENA_EVIDENCE_ARCHITECTURE.md §§1-5 ("Profile,
Growth and achievement read models"). A read model over the domain owners that
already exist, through the reads they already serve; it writes nothing, keeps
no copy and invents no measure. No surface calls it yet.

The rules it keeps, each from the contract:

- **Domains stay separate.** Writing, Reading, Listening, Speaking, Grammar and
  kept language each report their own measures. Nothing is averaged into one
  score: a CEFR estimate, a dictation match and a comprehension ratio are not
  one number.
- **Activity is labelled as activity.** A count of submitted versions is never
  renamed progress or proficiency.
- **Observations are real, attributed and honest about assistance.** Each
  carries its reference, its producer (evaluator, recogniser) and when it was
  observed. A line reconstructed after revealing the answer is `assisted`; a
  demonstration evaluator's number is `synthetic`, never a measurement.
- **Unknown is not zero.** An owner that cannot be read makes its domain
  `unavailable` and the whole summary `partial`. A record with no observation
  time is counted as `undated`, not placed in a window it may not belong to.
- **Growth only where measurements are comparable.** A trend needs the same
  metric, evaluator version, assistance mode and task family on both sides
  (`reference_backbone.growth_comparable`). Nothing recorded today says whether
  a piece was assisted, so no domain claims a trend yet; each says why.
- **No approved achievement policy, no achievements.** The catalogue is
  `unavailable`, empty, with that reason - not seeded awards.

Policy version `learner-summary/1` names these rules; a change to what counts
or how is a new version, not a silent edit.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

POLICY_VERSION = 'learner-summary/1'
WINDOWS = {'7d': 7, '30d': 30, '90d': 90, 'all': None}
DOMAINS = ('writing', 'reading', 'listening', 'speaking', 'grammar', 'language')
LATEST = 3
_log = logging.getLogger(__name__)

# What stands between every domain and a trend today. Named per domain so a
# surface can say something true rather than showing an empty chart.
GROWTH_UNAVAILABLE = {
    'writing': 'assistance_mode_unrecorded',
    'reading': 'assistance_mode_unrecorded',
    'listening': 'no_repeated_comparable_measure',
    'speaking': 'assistance_mode_unrecorded',
    'grammar': 'no_measure',
    'language': 'no_measure',
}
SYNTHETIC_EVALUATORS = {'fallback-demo'}


class SummaryRequestError(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Source:
    """One domain owner's existing read, and its bound when it has one.

    A read that fills its bound may have more, so that domain's counts become
    lower bounds (`countKind: at_least`) and the summary is `partial`.
    """

    domain: str
    read: Callable[[], Any]
    bound: int | None = None


def _instant(value: Any) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


class _Tally:
    """Counts inside the window, and records with no time kept apart."""

    def __init__(self, start: datetime | None, end: datetime):
        self.start, self.end = start, end
        self.count = 0
        self.undated = 0
        self.last: datetime | None = None

    def add(self, observed: datetime | None) -> bool:
        if observed is None:
            self.undated += 1
            return False
        if self.start is not None and not (self.start <= observed <= self.end):
            return False
        self.count += 1
        self.last = observed if self.last is None or observed > self.last else self.last
        return True

    def activity(self, label: str) -> dict[str, Any]:
        return {
            'label': label,
            'count': self.count,
            'undated': self.undated,
            'lastObservedAt': self.last.isoformat() if self.last else None,
        }


def _writing(rows: Sequence[Mapping[str, Any]], tally: _Tally) -> dict[str, Any]:
    observations = []
    for row in sorted(rows, key=lambda r: str(r.get('created_at') or ''), reverse=True):
        observed = _instant(row.get('created_at'))
        if not tally.add(observed):
            continue
        evaluator = str(row.get('evaluator') or '')
        overall = _number(row.get('overall'))
        if len(observations) < LATEST and overall is not None:
            observations.append({
                'ref': {'domain': 'writing', 'id': str(row.get('id'))},
                'measure': 'overall',
                'value': overall,
                'scale': '0-100',
                'levelEstimate': str(row.get('cefr_estimate') or row.get('level_estimate') or '') or None,
                'producer': evaluator or None,
                'synthetic': evaluator in SYNTHETIC_EVALUATORS,
                'assisted': None,
                'observedAt': observed.isoformat() if observed else None,
            })
    return {'activity': tally.activity('submitted_versions'), 'observations': observations}


def _reading(rows: Sequence[Mapping[str, Any]], tally: _Tally) -> dict[str, Any]:
    """Canonical Reading attempts only (D-082, D-083): the archived generated
    sessions are not an earlier practice this summary shows."""
    observations = []
    for row in rows:
        total = int(row.get('total') or 0)
        if total <= 0:
            continue
        observed = _instant(row.get('created_at'))
        in_window = tally.add(observed)
        if (in_window or observed is None) and len(observations) < LATEST:
            observations.append({
                'ref': {'domain': 'reading', 'id': str(row.get('id'))},
                'measure': 'comprehension_matched',
                'value': {'correct': int(row.get('correct_count') or 0), 'total': total},
                'producer': 'reading-attempt',
                'synthetic': False,
                'assisted': None,
                'observedAt': observed.isoformat() if observed else None,
            })
    return {'activity': tally.activity('checks_answered'), 'observations': observations}


def _listening(rows: Sequence[Mapping[str, Any]], tally: _Tally) -> dict[str, Any]:
    observations = []
    for row in sorted(rows, key=lambda r: str(r.get('updated_at') or ''), reverse=True):
        if not int(row.get('checked_attempt_count') or 0) and not row.get('revealed'):
            continue
        observed = _instant(row.get('updated_at'))
        if not tally.add(observed):
            continue
        accuracy = _number(row.get('best_accuracy_percent'))
        if len(observations) < LATEST and accuracy is not None:
            observations.append({
                'ref': {'domain': 'listening', 'id': f"{row.get('asset_id')}#{row.get('segment_id')}"},
                'measure': 'dictation_best_match',
                'value': accuracy,
                'scale': '0-100',
                'producer': 'dictation-comparison',
                'synthetic': False,
                # Revealing the line makes any later match assisted.
                'assisted': bool(row.get('revealed')),
                'observedAt': observed.isoformat() if observed else None,
            })
    return {'activity': tally.activity('lines_reconstructed'), 'observations': observations}


def _speaking(rows: Sequence[Mapping[str, Any]], tally: _Tally) -> dict[str, Any]:
    observations = []
    for row in sorted(rows, key=lambda r: str(r.get('created_at') or ''), reverse=True):
        observed = _instant(row.get('created_at'))
        if not tally.add(observed):
            continue
        if len(observations) >= LATEST:
            continue
        dimensions = row.get('dimensions') or {}
        provenance = row.get('provenance') or {}
        synthetic = bool((row.get('evidence') or {}).get('synthetic_demo'))
        measured = {
            name: _number(value)
            for name, value in dimensions.items()
            if _number(value) is not None
        }
        observations.append({
            'ref': {'domain': 'speaking', 'id': str(row.get('take_id') or row.get('id'))},
            'measure': 'speaking_dimensions',
            'value': measured,
            # Not measured, not applicable and not assessed stay distinct.
            'status': {name: provenance.get(name) for name in dimensions if name not in measured},
            'producer': {name: provenance.get(name) for name in measured},
            'synthetic': synthetic,
            'assisted': None,
            'observedAt': observed.isoformat() if observed else None,
        })
    return {'activity': tally.activity('takes'), 'observations': observations}


def _grammar(completed: Any, tally: _Tally) -> dict[str, Any]:
    for _ in sorted(completed or ()):
        tally.add(None)
    return {'activity': tally.activity('patterns_marked_complete'), 'observations': []}


def _language(rows: Sequence[Mapping[str, Any]], tally: _Tally) -> dict[str, Any]:
    recalls = 0
    for row in rows:
        tally.add(_instant(row.get('added_at')))
        recalls += int(row.get('successful_recalls') or 0)
    return {
        'activity': tally.activity('phrases_kept'),
        'observations': [{
            'ref': {'domain': 'language', 'id': '*'},
            'measure': 'successful_recalls_all_time',
            'value': recalls,
            'producer': 'recall-self-assessment',
            'synthetic': False,
            'assisted': None,
            'observedAt': None,
        }] if rows else [],
    }


READERS = {
    'writing': _writing,
    'reading': _reading,
    'listening': _listening,
    'speaking': _speaking,
    'grammar': _grammar,
    'language': _language,
}


def learner_summary(
    language: str,
    sources: Sequence[Source],
    *,
    window: str = '30d',
    now: datetime | None = None,
) -> dict[str, Any]:
    """`LearnerSummary(scope, window, policyVersion)`."""
    if window not in WINDOWS:
        raise SummaryRequestError('window_unknown')
    language = str(language or '').strip().casefold()
    if not language:
        raise SummaryRequestError('language_required')
    end = now or datetime.now(UTC)
    days = WINDOWS[window]
    start = end - timedelta(days=days) if days else None

    domains: dict[str, Any] = {}
    unavailable: list[str] = []
    truncated: list[str] = []
    for source in sources:
        if source.domain not in READERS:
            raise SummaryRequestError('domain_unknown')
        try:
            raw = source.read()
            body = READERS[source.domain](raw, _Tally(start, end))
        except Exception as error:
            _log.warning('learner summary domain %s unavailable: %s', source.domain, type(error).__name__)
            unavailable.append(source.domain)
            domains[source.domain] = {'status': 'unavailable'}
            continue
        at_least = source.bound is not None and len(raw or ()) >= source.bound
        body['activity']['countKind'] = 'at_least' if at_least else 'exact'
        if at_least:
            truncated.append(source.domain)
        has_evidence = body['activity']['count'] or body['activity']['undated'] or body['observations']
        domains[source.domain] = {
            'status': 'current' if has_evidence else 'empty',
            **body,
            'growth': {'status': 'unavailable', 'reason': GROWTH_UNAVAILABLE[source.domain]},
        }

    any_evidence = any(domain.get('status') == 'current' for domain in domains.values())
    outcome = 'partial' if unavailable or truncated else ('current' if any_evidence else 'empty')
    return {
        'policyVersion': POLICY_VERSION,
        'learningLanguage': language,
        'window': {'kind': window, 'from': start.isoformat() if start else None, 'to': end.isoformat()},
        'outcome': outcome,
        'unavailableDomains': unavailable,
        'truncatedDomains': truncated,
        'domains': domains,
        'achievements': {'status': 'unavailable', 'reason': 'no_approved_policy', 'items': []},
    }
