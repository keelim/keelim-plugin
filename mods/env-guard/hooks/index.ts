import type { Register } from 'claude-code'

// `.env`, `.env.local`, `apps/web/.env.production`; not `.envrc` or `env.ts`.
const PROTECTED = /(^|\/)\.env(\.[^/]*)?$/

const denial = (plugin: string, path: string) =>
  PROTECTED.test(path) ? { deny: `${plugin}: ${path} holds secrets and is protected.` } : undefined

// Matchers stay literal so `claude plugin validate` lists each guarded tool.
export const register: Register = on => {
  on('tool.call', { tool: 'Read' }, ($, e, next) => denial($.plugin.name, e.file_path) ?? next(e))
    .catch(($, e, next) => (next.called ? next(e) : { deny: `${$.plugin.name}: its guard failed.` }))
  on('tool.call', { tool: 'Edit' }, ($, e, next) => denial($.plugin.name, e.file_path) ?? next(e))
    .catch(($, e, next) => (next.called ? next(e) : { deny: `${$.plugin.name}: its guard failed.` }))
  on('tool.call', { tool: 'Write' }, ($, e, next) => denial($.plugin.name, e.file_path) ?? next(e))
    .catch(($, e, next) => (next.called ? next(e) : { deny: `${$.plugin.name}: its guard failed.` }))
}
