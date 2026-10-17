# Compare candidates before applying

## Context

Optimization and packaging can change behavior beyond metadata.

## Decision and alternatives

Default promotion to comparison and apply only a reviewed candidate; do not treat scores or capability metadata as authorization.

## Consequences

Preserve workflow gates/resources and run local validation before promotion; live effects still need their own authorization.
