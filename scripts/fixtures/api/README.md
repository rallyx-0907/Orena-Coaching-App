# Captured API payloads

Responses captured from the running application, so the new UI's screen gates
read the shape the backend really returns instead of a shape a test assumed.
A screen model that reads a field these payloads do not carry fails its gate.

Rules:

- Captured, not written: each file is a real response from the isolated
  verification stack (throwaway PostgreSQL, the seeded catalogue, the test
  learner), saved as returned. Trim long arrays only, never rename or add keys.
- No secrets and no real learner data: catalogue metadata and the seeded test
  learner only.
- Re-capture when the backend serializer changes; the file name says the route
  and its query.

| File | Route | Captured |
| --- | --- | --- |
| `listening_library.en.json` | `GET /api/listening/library?language=en` | 2026-09-28 |
