/** DESIGN-01 / D-064: deterministic UI stars, not cultural glyphs or AI assets.
 * Run: node miniprogram/tools/generate-character-icons.cjs
 * Uses the project's existing Playwright/Edge to rasterize local vectors only.
 */
const fs = require('node:fs')
const path = require('node:path')
const { createRequire } = require('node:module')
const root = path.resolve(__dirname, '../..')
const { chromium } = createRequire(path.join(root, 'web/package.json'))('@playwright/test')
const star = 'M12 2.5 14.9 8.4 21.4 9.4 16.7 14 17.8 20.5 12 17.4 6.2 20.5 7.3 14 2.6 9.4 9.1 8.4Z'
async function main() {
  const output = path.join(root, 'miniprogram/assets/icons')
  fs.mkdirSync(output, { recursive: true })
  const browser = await chromium.launch({ headless: true, channel: 'msedge' })
  try {
    const page = await browser.newPage({ viewport: { width: 72, height: 72 }, deviceScaleFactor: 1 })
    await page.route('**/*', route => route.abort())
    for (const selected of [false, true]) {
      const color = selected ? '#ad3024' : '#857c6f'
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="0 0 24 24"><path d="${star}" fill="${selected ? color : 'none'}" stroke="${color}" stroke-width="1.6" stroke-linejoin="round"/></svg>`
      await page.setContent(`<style>html,body{margin:0;width:72px;height:72px;background:transparent}img{display:block;width:72px;height:72px}</style><img src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}">`)
      await page.locator('img').evaluate(image => image.decode())
      const file = path.join(output, selected ? 'favorite-filled.png' : 'favorite-outline.png')
      await page.screenshot({ path: file, omitBackground: true })
      console.log(path.relative(root, file) + ': ' + fs.statSync(file).size + ' bytes')
    }
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
