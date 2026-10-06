/** SHARE-01 / DESIGN-01. Offline WXML layout checks, NOT WeChat/AI integration evidence.
 * node miniprogram/tests/poster-visual.cjs
 * Screenshots go to the OS temporary directory; no shared files are modified.
 */
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const assert = require('node:assert/strict')
const os = require('node:os')
const { createRequire } = require('node:module')
const root = path.resolve(__dirname, '../..')
const mini = path.join(root, 'miniprogram')
const dependencies = createRequire(path.join(root, 'web/package.json'))
const { parse } = dependencies('@vue/compiler-dom')
const read = file => fs.readFileSync(path.join(mini, file), 'utf8')
const escape = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const evaluate = (expression, scope) => vm.runInNewContext(expression, scope, { timeout: 100 })
const value = (text, scope) => /^\{\{[^]*\}\}$/.test(text) && (text.match(/\{\{/g) || []).length === 1
  ? evaluate(text.slice(2, -2), scope)
  : text.replace(/\{\{([^]*?)\}\}/g, (_, js) => evaluate(js, scope) ?? '')
const attrs = node => Object.fromEntries(node.props.filter(p => p.type === 6).map(p => [p.name, p.value?.content ?? '']))
const trees = new Map()
function tree(file) {
  if (!trees.has(file)) trees.set(file, parse(read(file), { comments: false }).children)
  return trees.get(file)
}
function asset(src) {
  if (!src) return ''
  if (src.startsWith('data:image/')) return src
  if (src.startsWith('/assets/')) {
    return 'data:' + (src.endsWith('.jpg') ? 'image/jpeg' : 'image/png') + ';base64,' + fs.readFileSync(path.join(mini, src)).toString('base64')
  }
  // Unit/visual fixtures never fetch remote images or fabricate approved glyphs.
  return ''
}
function children(nodes, scope) {
  let html = '', chain = false, taken = false
  for (const node of nodes) {
    if (node.type === 1) {
      const a = attrs(node)
      if ('wx:if' in a) { chain = true; taken = !!value(a['wx:if'], scope); if (!taken) continue }
      else if ('wx:elif' in a) { if (!chain || taken || !value(a['wx:elif'], scope)) continue; taken = true }
      else if ('wx:else' in a) { if (!chain || taken) continue; taken = true }
      else { chain = false; taken = false }
    }
    html += render(node, scope)
  }
  return html
}
function render(node, scope, loop = false) {
  if (node.type === 2) return escape(node.content)
  if (node.type === 5) return escape(evaluate(node.content.content, scope))
  if (node.type !== 1) return ''
  const a = attrs(node)
  if (!loop && a['wx:for']) return (value(a['wx:for'], scope) || []).map((item, index) => render(node, { ...scope, item, index }, true)).join('')
  if (node.tag === 'block') return children(node.children, scope)
  if (['glyph-image', 'view-state'].includes(node.tag)) {
    const props = { src: '', failed: false, loading: false, error: '', empty: false, emptyText: '', requestId: '' }
    for (const [key, val] of Object.entries(a)) if (!key.startsWith('bind')) props[key.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value(val, scope)
    // Empty fixture URLs render the real missing-glyph component, never invented cultural imagery.
    props.src = asset(props.src)
    return `<div class="component-${node.tag}">${children(tree(`components/${node.tag}/index.wxml`), props)}</div>`
  }
  const tag = ({ view: 'div', text: 'span', image: 'img', 'scroll-view': 'div' })[node.tag] || node.tag
  let attributes = ''
  for (const [key, raw] of Object.entries(a)) {
    if (/^(wx:|bind|catch)/.test(key)) continue
    const val = value(raw, scope)
    if (['disabled', 'loading'].includes(key)) { if (val) attributes += ` ${key}`; continue }
    if (node.tag === 'textarea' && key === 'value') continue
    attributes += ` ${key}="${escape(key === 'src' ? asset(val) : val)}"`
  }
  if (a.bindtap) attributes += ` data-handler="${escape(a.bindtap)}"`
  if (tag === 'img') return `<img${attributes} style="object-fit:${a.mode === 'aspectFill' ? 'cover' : 'contain'}">`
  return `<${tag}${attributes}>${tag === 'textarea' ? escape(value(a.value || '', scope)) : children(node.children, scope)}</${tag}>`
}
function initialData() {
  let data
  vm.runInNewContext(read('pages/poster/index.js'), { require: () => ({}), Page: page => { data = page.data } })
  return JSON.parse(JSON.stringify(data))
}
function renderPoster(data) { return children(tree('pages/poster/index.wxml'), { ...initialData(), ...data }) }
function css(width) {
  return ['app.wxss', 'components/view-state/index.wxss', 'components/glyph-image/index.wxss', 'pages/poster/index.wxss']
    .map(read).join('\n').replace(/(-?\d*\.?\d+)rpx/g, (_, n) => `${Number(n) * width / 750}px`)
    .replace(/(^|[}\s])page(?=\s*\{)/g, '$1body')
    .replace(/(^|[\s,>+~])(view|text|image)(?=[\s,.#:\[>+~{])/g, (_, prefix, tag) => prefix + ({ view: 'div', text: 'span', image: 'img' })[tag])
    .replace(/:host/g, '.component-glyph-image')
}
async function main() {
  const { chromium } = dependencies('@playwright/test')
  const browser = await chromium.launch({ headless: true, channel: 'msedge' })
  const output = fs.mkdtempSync(path.join(os.tmpdir(), 'poster-visual-'))
  let checks = 0
  try {
    const items = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬'].map((name, index) => ({ id: `fixture-${index}`, cn_name: `布局${name}`, image_url: '', selected: [2, 0, 1].includes(index), order: [2, 0, 1].indexOf(index) + 1 }))
    const base = { ...initialData(), loading: false, items, selected: ['fixture-2', 'fixture-0', 'fixture-1'], selectedItems: [items[2], items[0], items[1]] }
    // Completed is a labeled test image, never evidence of real AI artwork.
    const fixturePNG = dependencies('pngjs').PNG
    const png = new fixturePNG({ width: 240, height: 360 })
    for (let i = 0; i < png.data.length; i += 4) { png.data[i] = 244; png.data[i + 1] = 235; png.data[i + 2] = 219; png.data[i + 3] = 255 }
    const image = 'data:image/png;base64,' + fixturePNG.sync.write(png).toString('base64')
    const states = [
      ['draft', base], ['one', { ...base, selected: [items[0].id], selectedItems: [items[0]] }],
      ['unselected', { ...base, selected: [], selectedItems: [] }],
      ['queued', { ...base, generating: true, status: 'queued' }],
      ['generating', { ...base, generating: true, status: 'generating' }],
      ['downloading', { ...base, generating: true, status: 'downloading' }],
      ['failed', { ...base, status: 'failed', canRetry: true, error: '海报生成暂未开通，请稍后再来。' }],
      ['terminal-failed', { ...base, status: 'failed', canRetry: true, terminalFailure: true, error: '海报生成超时，可稍后重新生成。' }],
      ['paused', { ...base, status: 'paused', canRetry: true, error: '等待已超过五分钟。可继续查询原任务，无需重新生成。' }],
      ['completed', { ...base, status: 'completed', image, shareCode: false }],
      ['completed-code', { ...base, status: 'completed', image, shareCode: true }],
      ['saving', { ...base, status: 'completed', image, saving: true }],
      ['empty', { ...base, items: [] }], ['loading', { ...base, loading: true }],
      ['unauthorized', { ...base, items: [], loadError: '请先登录，再来制作印记。' }],
      ['long', { ...base, caption: '很长的旅途记忆'.repeat(7).slice(0, 50), captionLength: 50, selectedItems: base.selectedItems.map(item => ({ ...item, cn_name: '长词条排版检查'.repeat(4) })) }],
      ...['mountain', 'old-town', 'minimal'].map(template => [template, { ...base, template }])
    ]
    for (const width of [320, 375, 430]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } })
      const errors = []
      page.on('pageerror', error => errors.push(error.message))
      await page.route('**/*', route => route.abort())
      for (const [name, data] of states) {
        // Stress the native v2 button defaults, not merely browser defaults.
        const nativeButtons = 'button[size="mini"]{display:inline-block;margin-left:auto;margin-right:auto;padding:0 1.32em;font-size:13px;line-height:2.3}button:not([size="mini"]){width:184px;min-width:184px;margin:auto}'
        await page.setContent(`<html lang="zh-CN"><meta charset="UTF-8"><style>body{margin:0}button,textarea{font-family:inherit}textarea{resize:none;border:0;background:transparent}img{display:block} .gallery-scroll{overflow-y:auto} ${css(width)} ${nativeButtons}</style><body>${renderPoster(data)}</body></html>`)
        await page.evaluate(() => Promise.all(Array.from(document.images).map(img => img.decode().catch(() => {}))))
        const layout = await page.evaluate(() => ({
          overflow: document.documentElement.scrollWidth > innerWidth + 1,
          smallButtons: [...document.querySelectorAll('button,[data-handler]')].filter(el => el.getBoundingClientRect().height < 43.9 || el.getBoundingClientRect().width < 43.9).map(el => el.textContent),
          styles: document.querySelectorAll('.template').length,
          selected: [...document.querySelectorAll('.selected-glyph')].map(el => el.dataset.id),
          draft: [...document.querySelectorAll('.draft-word')].map(el => el.textContent.trim()),
          image: document.querySelector('.poster-image')?.getAttribute('src'),
          save: !!document.querySelector('.save-button'),
          missingCode: !!document.querySelector('.code-note'),
          previewText: document.querySelector('.preview-section')?.textContent || '',
          previewButton: document.querySelector('.poster-image')?.closest('button')?.dataset.handler,
          completedControls: [...document.querySelectorAll('.preview-button,.save-button,.share-button')].map(el => {
            const rect = el.getBoundingClientRect()
            return { control: el.className, width: rect.width, height: rect.height }
          })
        }))
        assert.equal(layout.overflow, false, `${width}/${name}: horizontal overflow`)
        assert.deepEqual(layout.smallButtons, [], `${width}/${name}: small touch targets`)
        assert.equal(layout.missingCode, false, `${width}/${name}: internal code annotation`)
        assert.doesNotMatch(layout.previewText, /小程序码|二维码|AI\s*(?:辅助|生成)?\s*背景/i, `${width}/${name}: implementation annotation`)
        if (data.items.length && !data.loading && !data.loadError) {
          assert.equal(layout.styles, 4)
          assert.deepEqual(layout.selected, data.selected)
          assert.equal(layout.save, !!data.image)
          if (data.image) { assert.equal(layout.image, data.image); assert.equal(layout.previewButton, 'preview') }
        }
        assert.deepEqual(errors, [])
        if (width === 375 && ['draft', 'completed', 'failed', 'terminal-failed', 'long'].includes(name)) {
          if (data.image) await page.locator('.poster-image').evaluate(el => { el.style.outline = '2px dashed #ad3026'; el.setAttribute('alt', 'OFFLINE PNG FIXTURE — NOT GENERATED ARTWORK') })
          await page.screenshot({ path: path.join(output, `${name}-${width}.png`), fullPage: true })
          const screenshot = path.join(output, `${name}-${width}.png`)
          const dimensions = fixturePNG.sync.read(fs.readFileSync(screenshot))
          console.log(JSON.stringify({ screenshot, width: dimensions.width, height: dimensions.height, bytes: fs.statSync(screenshot).size, styles: data.styles.map(style => style.id), previewButton: layout.previewButton || null, completedControls: layout.completedControls, targetsBelow44px: layout.smallButtons.length }))
        }
        checks += 1
      }
      await page.close()
    }
    console.log(JSON.stringify({ checks, widths: [320, 375, 430], screenshots: output, limitation: 'Offline approximations only; not WeChat or real generation verification.' }))
  } finally { await browser.close() }
}
module.exports = { renderPoster, initialData }
if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1 })
