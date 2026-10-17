# Skill capabilities and protected inputs

Protect credentials, private source material, session content, model traces, and external accounts accessed by individual skills. The collection has no common account system.

| Action | Required condition | Not authorized by |
| --- | --- | --- |
| Review workflow source | User's review scope | Availability of a production script |
| Local source edit or candidate application | Authorized scope and reviewed diff | Successful optimization score alone |
| External write or credential action | Owning skill's specific authorization and authenticated target | Capability metadata or installation |
| Hook installation | Explicit requested scope and reviewed registration | Merely validating hook files |

All skills declare boolean `read_only`, `local_write`, `network_read`, `external_write`, `credentials`, and `hooks`. Preserve accurate effect declarations and each skill's own safety gates. Do not add secrets, raw session logs, or one-off task status to durable workflow files. Keep optimization traces and candidates in ignored `.skillopt/` and redact evaluation material.

Authentication, expiry, revocation, and rotation belong to the connected provider and the owning skill. Missing credentials leave live readiness unverified; no global lifetime or recovery policy is defined. Do not run credential refresh or install hooks merely to prove metadata validity. Record candidate identity, reviewed diff, checks, application scope, and external-action evidence without secret values.
