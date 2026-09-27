"""Orena Intelligence: the agent that works above Orena's domain services (D-085).

The interface to the learner UI is `docs/project/AGENT_CONTRACT.md`; this
package implements it and never extends it (D-086). What holds everywhere here:

- The agent reads. Learner data changes only when the client runs an action
  through the app's existing APIs with the learner's session (contract §7).
- A tool calls an existing service. It never opens the database itself, and it
  never takes the learner from an argument a model produced (contract §2).
- Providers, credentials and routing belong to `writing_coach.ai`. Nothing here
  reads a provider key or puts a provider name in learner-facing text.
- Sessions live in a TTL cache in this process; conversation history and coach
  notes are device memory (AGENTS.md §7, spec D7). Nothing here is a table.

Slice 1a is these contracts, the registries, a deterministic fake provider and
the voice interfaces. No router is installed (`app.py` does not import this
package yet).
"""
