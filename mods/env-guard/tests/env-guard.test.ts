import { describe, expect, test } from 'claude-code/testing'

// Nothing sits beneath the plugin: this hook stands for the engine running the tool.
const engineRuns = { result: {} }

describe('env-guard', () => {
  for (const file_path of ['.env', '.env.local', 'apps/web/.env.production']) {
    test(`denies reading and writing ${file_path}`, async ($, on) => {
      on('tool.call', () => engineRuns)

      const read = await $.tool.call({ tool: 'Read', file_path })
      const edit = await $.tool.call({ tool: 'Edit', file_path, old_string: 'A', new_string: 'B' })
      const write = await $.tool.call({ tool: 'Write', file_path, content: 'A=1' })

      for (const answer of [read, edit, write]) expect(answer.deny).toContain(file_path)
    })
  }

  for (const file_path of ['README.md', '.envrc', 'src/env.ts', '.env.d/notes.md']) {
    test(`passes ${file_path} through`, async ($, on) => {
      on('tool.call', () => engineRuns)

      const edit = await $.tool.call({ tool: 'Edit', file_path, old_string: 'A', new_string: 'B' })

      expect(edit.deny).toBeUndefined()
    })
  }
})
