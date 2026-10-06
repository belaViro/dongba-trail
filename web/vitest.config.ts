import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      // Our in-memory renderer mounts client components, not SSR render functions.
      testTransformMode: { web: ['**/*.test.ts', '**/*.vue'] },
    },
  }),
)
