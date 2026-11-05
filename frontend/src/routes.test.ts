import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * The old "Four accelerators" overview page was removed on request: the app
 * opens on the Ontology tool, and /home only redirects there. These checks
 * keep it from quietly coming back.
 */
const src = resolve(__dirname)
const app = readFileSync(resolve(src, 'App.tsx'), 'utf-8')
const shell = readFileSync(resolve(src, 'layout/AppShell.tsx'), 'utf-8')

describe('app routes', () => {
  it('opens on the Ontology tool', () => {
    expect(app).toMatch(/<Route index element=\{<Navigate to="\/tools\/ontology" replace \/>\} \/>/)
  })

  it('keeps /home only as a redirect to the Ontology tool', () => {
    expect(app).toMatch(/path="home" element=\{<Navigate to="\/tools\/ontology" replace \/>\}/)
    expect(app).not.toMatch(/pages\/Home/)
    expect(existsSync(resolve(src, 'pages/Home.tsx'))).toBe(false)
  })

  it('has no sidebar link to the removed page', () => {
    expect(shell).not.toMatch(/to: '\/home'/)
    expect(shell).not.toMatch(/Four tools/)
  })
})
