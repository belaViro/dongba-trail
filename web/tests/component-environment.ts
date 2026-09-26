import type { Environment } from 'vitest/environments'

// Compile Vue SFCs for a client renderer without installing a DOM or running a browser.
export default {
  name: 'component-memory',
  transformMode: 'web',
  setup() {
    return { teardown() {} }
  },
} satisfies Environment
