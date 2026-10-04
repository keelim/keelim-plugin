# Workflow ownership and promotion

Each skill has one maintained source folder and a specific trigger. A review request inspects the requested concern; it does not invoke that skill's production workflow. Recommendations name the skill, relevant section, visible evidence, and concrete checks/resources actually present.

Capability metadata describes possible effects, not user authorization. `read_only: true` cannot coexist with local writes, external writes, or hooks. A skill's offline, source, publication, and production-verification promises survive refactoring or movement.

A candidate is not production source. Compare the candidate with current content before applying it; preserve front matter and bundled resources. A no-diff result is not an improvement. Catalog output reflects source metadata and is not edited as an independent workflow specification.

A symlink installation follows source edits; a copied installation is a snapshot and needs an explicit refresh. The personal ChatGPT `sleeping` copy is a separate installation: preserve its identity during an authorized update rather than deleting or duplicating it.
