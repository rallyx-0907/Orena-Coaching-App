from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def req(ok,msg):
    if not ok: raise SystemExit('Specialized persistence boundary validation FAILED: '+msg)
def text(rel): return (ROOT/rel).read_text(encoding='utf-8')
req((ROOT/'VERSION').read_text().strip() == '1.4.0','VERSION must be v1.4.0')
app=text('app.py'); repo=text('writing_coach/persistence/specialized_repository.py')
for name in ['becoming_memory.py','becoming_outcomes.py','becoming_library.py','becoming_linguistics.py']:
    src=text('writing_coach/'+name)
    req('_repo()' in src or '_repository' in src, name+' must use repository boundary')
    # Runtime service logic must not own connection factories anymore.
    req('_db_factory' not in src and 'def _db()' not in src, name+' still owns DB factory')
for name in ['becoming_memory.py','becoming_library.py']:
    src=text('writing_coach/'+name)
    for forbidden in ['import sqlite3','sqlite3.Connection','CREATE TABLE','ALTER TABLE','PRAGMA']:
        req(forbidden not in src,name+' still owns SQLite schema detail: '+forbidden)
# Was: require app.py to construct SQLiteSpecializedLearningRepository.
# That froze SQLite as the active backend, which the v1.4.0 cutover has since
# superseded -- PostgreSQL is authoritative. The boundary that still matters is
# that the implementation is chosen centrally by build_runtime, and that app.py
# never constructs one itself.
runtime = text('writing_coach/persistence/runtime.py')
req('PostgresSpecializedLearningRepository(' in runtime
    and 'SQLiteSpecializedLearningRepository(' in runtime,
    'central runtime must offer both specialized repository implementations')
req('SQLiteSpecializedLearningRepository(' not in app
    and 'PostgresSpecializedLearningRepository(' not in app,
    'app.py must not construct a specialized repository; build_runtime selects it')
core_init=app.find('_learning_repository.initialize(schema_version=SCHEMA_VERSION)')
specialized_init=app.find('_specialized_learning_repository.initialize()')
cache_init=app.find('_learning_cache.initialize()')
req(core_init >= 0 and specialized_init >= 0 and cache_init >= 0,'v1.3.4 repository initialization call missing')
req(core_init < specialized_init < cache_init,'v1.3.4 repository initialization order must be core, specialized, cache')
req('PostgresSpecializedLearningRepository' in repo,'PostgreSQL specialized repository implementation missing')
req('create_shadow_engine' in repo,'PostgreSQL specialized repository is not SQLAlchemy-backed')
protocol=repo.split('class SQLiteSpecializedLearningRepository',1)[0]
postgres=repo.split('class PostgresSpecializedLearningRepository',1)[1]
req('def initialize(self)' not in protocol,'domain repository protocol must not own schema lifecycle')
req('def initialize(self)' in repo.split('class SQLiteSpecializedLearningRepository',1)[1].split('class PostgresSpecializedLearningRepository',1)[0],'SQLite specialized repository must own schema initialization')
req('def initialize(self)' not in postgres,'PostgreSQL specialized repository must remain Alembic-owned')
req('configure_becoming_memory(_specialized_learning_repository)' in app,'memory not wired to repository')
req('configure_becoming_outcomes(_specialized_learning_repository)' in app,'outcomes not wired to repository')
req('configure_becoming_library(_specialized_learning_repository)' in app,'library not wired to repository')
# The generated-reading service is retired (D-082); canonical Reading has its
# own repository, ReadingEvidenceRepository, wired with the Reading engine.
req('configure_becoming_reading' not in app,'the retired generated-reading service is wired again')
req('ReadingEvidenceRepository(engine)' in app,'canonical Reading evidence is not wired')
req('configure_becoming_linguistics(_specialized_learning_repository)' in app,'linguistics not wired to repository')
req((ROOT/'docs/SPECIALIZED_PERSISTENCE_BOUNDARY.md').exists(),'missing boundary doc')
print('BECOMING specialized persistence boundary validation OK')
print('Memory / Outcomes / Active Recall / Linguistics: repository-bound; Reading: canonical evidence')
print('Specialized SQLite schema ownership: repository-bound')
print('SQLite specialized repository: FROZEN ROLLBACK / ARCHIVE ONLY')
print('PostgreSQL specialized repository: AUTHORITATIVE')
print('Runtime cutover: COMPLETE')
