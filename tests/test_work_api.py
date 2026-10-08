"""The first I2 write path: `/api/account-backbone` and `/api/works`.

The hermetic half checks that nothing is served, and nothing claims to be
saved, unless the backbone is `active`. The PostgreSQL half (skipped unless
`ORENA_TEST_POSTGRES_URL` names a throwaway database) runs the routes against
real repositories: create, read back, a lost acknowledgment replayed, a stale
edit refused with the server's text, another language and another account not
found, the change stream, and a deleted account meeting the barrier.
"""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest

pytest.importorskip('fastapi')
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from writing_coach import work_api  # noqa: E402
from writing_coach.account_backbone import DISABLED, UNAVAILABLE, AccountBackbone  # noqa: E402


def _client(backbone, *, user='learner-a', language='en'):
    who = {'user': user, 'language': language}
    work_api.configure_work(backbone, user_key=lambda: who['user'], language=lambda: who['language'])
    app = FastAPI()
    app.include_router(work_api.router)
    return TestClient(app), who


@pytest.fixture(autouse=True)
def _reset():
    yield
    work_api.configure_work(AccountBackbone(DISABLED))


@pytest.mark.parametrize('state', [DISABLED, UNAVAILABLE])
def test_nothing_is_served_or_claimed_unless_the_backbone_is_active(state):
    client, _ = _client(AccountBackbone(state))
    assert client.get('/api/account-backbone').json() == {'state': state}
    ident = str(uuid.uuid4())
    for response in (
        client.get(f'/api/works/{ident}'),
        client.put(f'/api/works/{ident}', json={'operationId': 'op-12345678', 'expectedVersion': 0}),
        client.get('/api/works/changes'),
    ):
        assert response.status_code == 503
        assert response.json()['detail']['category'] == f'account_backbone_{state}'


# --- PostgreSQL --------------------------------------------------------------

URL = os.getenv('ORENA_TEST_POSTGRES_URL', '')
postgres = pytest.mark.skipif(not URL, reason='ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run')


@pytest.fixture(scope='module')
def engine():
    if not URL:
        pytest.skip('ORENA_TEST_POSTGRES_URL is not set')
    from alembic import command
    from sqlalchemy import create_engine
    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option('sqlalchemy.url', URL.replace('%', '%%'))
    command.upgrade(cfg, 'head')
    engine = create_engine(URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def active(engine):
    from sqlalchemy import inspect
    from writing_coach.account_backbone import build_backbone

    backbone = build_backbone(engine, inspect(engine).get_table_names(), env={'ORENA_ACCOUNT_BACKBONE': 'on'})
    assert backbone.is_active
    return backbone


def _user(engine, key):
    from sqlalchemy import text
    from writing_coach.persistence.ids import stable_uuid

    with engine.begin() as connection:
        connection.execute(
            text(
                'INSERT INTO users (id, user_key, email, name, picture, role, created_at) '
                "VALUES (:id, :key, '', '', '', 'user', :now) ON CONFLICT DO NOTHING"
            ),
            {'id': stable_uuid('user', key), 'key': key, 'now': datetime.now(UTC)},
        )
    return str(stable_uuid('user', key))


def _put(client, ident, version, text_, *, op=None, kind='draft'):
    return client.put(f'/api/works/{ident}', json={
        'operationId': op or f'op-{uuid.uuid4()}', 'expectedVersion': version, 'kind': kind,
        'payload': {'text': text_},
    })


@postgres
def test_a_draft_is_kept_with_the_account_and_a_lost_acknowledgment_replays(engine, active):
    key = f'work-{uuid.uuid4()}'
    _user(engine, key)
    client, _ = _client(active, user=key)
    assert client.get('/api/account-backbone').json() == {'state': 'active'}
    ident, op = str(uuid.uuid4()), f'op-{uuid.uuid4()}'

    first = _put(client, ident, 0, 'Dear Anna,', op=op)
    assert first.status_code == 200 and first.json()['status'] == 'committed' and first.json()['version'] == 1
    again = _put(client, ident, 0, 'Dear Anna,', op=op)
    assert again.status_code == 200 and again.json()['status'] == 'replay' and again.json()['version'] == 1

    work = client.get(f'/api/works/{ident}').json()['work']
    assert work['payload'] == {'text': 'Dear Anna,'} and work['version'] == 1 and work['language'] == 'en'

    assert _put(client, ident, 1, 'Dear Anna, thank you').json()['version'] == 2
    stale = _put(client, ident, 1, 'Dear Anna, sorry')
    assert stale.status_code == 409
    detail = stale.json()['detail']
    assert detail['category'] == 'work_conflict'
    assert detail['context'] == {'serverVersion': 2, 'serverPayload': {'text': 'Dear Anna, thank you'}}

    changes = client.get('/api/works/changes').json()
    assert [c['version'] for c in changes['changes'] if c['id'] == ident] == [1, 2]
    assert changes['more'] is False
    later = client.get(f'/api/works/changes?after={changes["after"]}').json()
    assert later['changes'] == []


@postgres
def test_another_language_or_account_does_not_find_it(engine, active):
    owner, stranger = f'work-{uuid.uuid4()}', f'work-{uuid.uuid4()}'
    _user(engine, owner)
    _user(engine, stranger)
    client, who = _client(active, user=owner)
    ident = str(uuid.uuid4())
    assert _put(client, ident, 0, '你好').status_code == 200

    who['language'] = 'zh'
    assert client.get(f'/api/works/{ident}').status_code == 404
    assert _put(client, ident, 1, '改').status_code == 404

    who.update(user=stranger, language='en')
    assert client.get(f'/api/works/{ident}').status_code == 404
    response = _put(client, ident, 1, 'mine now')
    assert response.status_code == 404 and response.json()['detail']['category'] == 'work_not_found'
    assert all(c['id'] != ident for c in client.get('/api/works/changes').json()['changes'])


@postgres
def test_a_deleted_account_meets_the_barrier(engine, active):
    key = f'work-{uuid.uuid4()}'
    account = _user(engine, key)
    client, _ = _client(active, user=key)
    ident = str(uuid.uuid4())
    assert _put(client, ident, 0, 'before').status_code == 200
    active.incarnations.mark_deleted(active.incarnations.resolve(account))
    for response in (client.get(f'/api/works/{ident}'), _put(client, str(uuid.uuid4()), 0, 'after')):
        assert response.status_code == 403 and response.json()['detail']['category'] == 'account_deleted'
    assert active.incarnations.resolve(account) is None, 'no new incarnation was created'


@postgres
def test_bad_input_is_refused_before_anything_is_written(engine, active):
    key = f'work-{uuid.uuid4()}'
    _user(engine, key)
    client, _ = _client(active, user=key)
    assert client.get('/api/works/not-a-uuid').status_code == 422
    assert _put(client, str(uuid.uuid4()), 0, 'x', kind='essay').status_code == 422
    huge = client.put(f'/api/works/{uuid.uuid4()}', json={
        'operationId': f'op-{uuid.uuid4()}', 'expectedVersion': 0,
        'payload': {'text': 'x' * (work_api.MAX_PAYLOAD_CHARS + 1)},
    })
    assert huge.status_code == 413
    assert client.get('/api/works/changes').json()['changes'] == []


@postgres
def test_an_account_without_its_user_row_is_not_invented(engine, active):
    client, _ = _client(active, user=f'nobody-{uuid.uuid4()}')
    response = client.get(f'/api/works/{uuid.uuid4()}')
    assert response.status_code == 409 and response.json()['detail']['category'] == 'account_not_ready'


@postgres
def test_a_draft_follows_its_piece_across_devices_and_nowhere_else(engine, active):
    owner, stranger = f'work-{uuid.uuid4()}', f'work-{uuid.uuid4()}'
    _user(engine, owner)
    _user(engine, stranger)
    # One route configuration; `who` is whoever the next request is from.
    client, who = _client(active, user=owner)
    key = f'essay:{uuid.uuid4().int % 10_000}'
    assert client.get(f'/api/drafts/{key}').status_code == 404

    body = {'operationId': f'op-{uuid.uuid4()}', 'expectedVersion': 0, 'text': 'Dear Anna,', 'task': 'a letter'}
    assert client.put(f'/api/drafts/{key}', json=body).json() == {'status': 'committed', 'version': 1}
    assert client.put(f'/api/drafts/{key}', json=body).json() == {'status': 'replay', 'version': 1}

    # Another device of the same account and language reads the same draft
    # (the server, not the device, knows which work it is) and moves it on.
    assert client.get(f'/api/drafts/{key}').json() == {
        'draft': {'text': 'Dear Anna,', 'task': 'a letter', 'version': 1}}
    assert client.put(f'/api/drafts/{key}', json={
        'operationId': f'op-{uuid.uuid4()}', 'expectedVersion': 1, 'text': 'Dear Anna, hi'}).status_code == 200

    # The first device, still at version 1, is told what the other wrote.
    stale = client.put(f'/api/drafts/{key}', json={
        'operationId': f'op-{uuid.uuid4()}', 'expectedVersion': 1, 'text': 'Dear Anna, hello'})
    assert stale.status_code == 409
    assert stale.json()['detail']['context'] == {'serverVersion': 2, 'serverText': 'Dear Anna, hi', 'serverTask': ''}

    # Another language of the same account, and another account: their own.
    who['language'] = 'zh'
    assert client.get(f'/api/drafts/{key}').status_code == 404
    who.update(user=stranger, language='en')
    assert client.get(f'/api/drafts/{key}').status_code == 404
    assert client.put(f'/api/drafts/{key}', json={
        'operationId': f'op-{uuid.uuid4()}', 'expectedVersion': 0, 'text': 'mine'}).json()['version'] == 1
    who['user'] = owner
    assert client.get(f'/api/drafts/{key}').json()['draft']['text'] == 'Dear Anna, hi'


@postgres
def test_a_draft_over_the_rooms_limits_is_refused(engine, active):
    key = f'work-{uuid.uuid4()}'
    _user(engine, key)
    client, _ = _client(active, user=key)
    too_long = client.put('/api/drafts/expression:free', json={
        'operationId': f'op-{uuid.uuid4()}', 'expectedVersion': 0, 'text': 'x' * (work_api.DRAFT_TEXT_LIMIT + 1)})
    assert too_long.status_code == 422
    assert client.get('/api/drafts/expression:free').status_code == 404


@postgres
def test_a_new_incarnation_starts_with_no_draft_and_never_reaches_the_old_one(engine, active):
    """Review P1: the draft id left out the incarnation, so an explicit
    re-registration would have derived the old incarnation's work id."""
    from sqlalchemy import text

    key = f'work-{uuid.uuid4()}'
    account = _user(engine, key)
    client, _ = _client(active, user=key)
    piece = 'story:last-train'
    assert client.put(f'/api/drafts/{piece}', json={
        'operationId': f'op-{uuid.uuid4()}', 'expectedVersion': 0, 'text': 'old words', 'task': 'old task'}).status_code == 200
    old_incarnation = active.incarnations.resolve(account)

    active.incarnations.mark_deleted(old_incarnation)
    assert client.get(f'/api/drafts/{piece}').status_code == 403, 'the barrier holds'
    new_incarnation = active.incarnations.register_new(account)
    assert new_incarnation != old_incarnation

    assert client.get(f'/api/drafts/{piece}').status_code == 404, 'nothing of the old draft'
    fresh = client.put(f'/api/drafts/{piece}', json={
        'operationId': f'op-{uuid.uuid4()}', 'expectedVersion': 0, 'text': 'new words', 'task': ''})
    assert fresh.status_code == 200 and fresh.json() == {'status': 'committed', 'version': 1}
    assert client.get(f'/api/drafts/{piece}').json()['draft'] == {'text': 'new words', 'task': '', 'version': 1}

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT incarnation_id, payload, version FROM works "
                 "WHERE source_kind = 'item' AND source_id = :piece AND incarnation_id IN (:old, :new)"),
            {'piece': piece, 'old': old_incarnation, 'new': new_incarnation},
        ).mappings().all()
    by_incarnation = {str(row['incarnation_id']): row for row in rows}
    assert by_incarnation[old_incarnation]['payload'] == {'text': 'old words', 'task': 'old task'}
    assert by_incarnation[new_incarnation]['version'] == 1, 'two rows; the old one never attached'
