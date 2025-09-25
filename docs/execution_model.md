Dependency-Aware Execution Model

Goals
- Execute phases in parallel where possible while respecting `depends_on`.
- Surface readiness and progress via the event bus.

Implementation
- `lib/scheduler.py` implements topological ordering and readiness queues.
- Fan-in barriers are respected; cycles are detected and reported.

Events
- `phase.progress` and `task.status` should be emitted as phases start/complete/fail.

