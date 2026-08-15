# RetailEdge Agent Instructions

Before doing any RetailEdge task, always read and obey this file.

Do not continue R5.6 or any new feature work until the R5.5 candidate drift regression is fixed with failing regression tests first.

The most important invariant is:

Selected report row candidate == batch job row locked candidate == Bank Match Review candidate == confirmation candidate.

The backend may validate the locked candidate, but it must never replace it with current-best candidate.
