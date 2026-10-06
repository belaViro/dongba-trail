/** DESIGN-01: offline layout approximation, NOT a WeChat runtime or integration test.
 * Reads actual WXML/WXSS and renders fixture states in Chromium at phone widths.
 * Native map is intentionally a labeled placeholder; all network is blocked.
 * Run: node miniprogram/tests/visual-preview.cjs
 */
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const assert = require('node:assert/strict')
const { createRequire } = require('node:module')
const root = path.resolve(__dirname, '../..')
const dependencies = createRequire(path.join(root, 'web/package.json'))
const { parse } = dependencies('@vue/compiler-dom')
const { chromium } = dependencies('@playwright/test')
const mini = path.join(root, 'miniprogram')
const out = path.join(root, 'runtime/miniprogram-visual')
const homeOnly = process.argv.includes('--home')
const mapOnly = process.argv.includes('--map')
const resultOnly = process.argv.includes('--result')
const characterOnly = process.argv.includes('--character')
const questsOnly = process.argv.includes('--quests')
const questOnly = process.argv.includes('--quest')
const { questFixture } = require('./quest-fixtures.cjs')
const { questDetailFixture, configuredQuestFixtures } = require('./quest-detail-fixtures.cjs')
const appConfig = JSON.parse(fs.readFileSync(path.join(mini, 'app.json'), 'utf8'))
// Only tag selectors are translated: the previous /\bpage/ also broke .page.
const cssForBrowser = (css, width) => css.replace(/(-?\d*\.?\d+)rpx/g, (_, n) => `${Number(n) * width / 750}px`)
  .replace(/(^|[}\s])page(?=\s*\{)/g, '$1body')
  .replace(/(^|[\s,>+~])(view|text|image)(?=[\s,.#:\[>+~{])/g, (_, prefix, tag) => prefix + ({ view: 'div', text: 'span', image: 'img' })[tag])
  .replace(/:host/g, '.component-glyph-image')
const read = file => fs.readFileSync(path.join(mini, file), 'utf8')
const escape = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const evaluate = (expression, scope) => {
  try { return vm.runInNewContext(expression, scope, { timeout: 100 }) }
  catch (error) { if (error.name === 'TypeError' || error.name === 'ReferenceError') return undefined; throw error }
}
const expression = value => value.replace(/^\{\{|\}\}$/g, '')
const value = (text, scope) => /^\{\{[^]*\}\}$/.test(text) && (text.match(/\{\{/g) || []).length === 1
  ? evaluate(expression(text), scope)
  : text.replace(/\{\{([^]*?)\}\}/g, (_, js) => evaluate(js, scope) ?? '')
const assets = src => src && src.startsWith('/assets/')
  ? 'data:' + (src.endsWith('.jpg') ? 'image/jpeg' : 'image/png') + ';base64,' + fs.readFileSync(path.join(mini, src)).toString('base64') : ''
const trees = new Map()
const tree = file => {
  if (!trees.has(file)) trees.set(file, parse(read(file), { comments: false }).children)
  return trees.get(file)
}
const attrs = node => Object.fromEntries(node.props.filter(p => p.type === 6).map(p => [p.name, p.value?.content ?? '']))
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
  if (!loop && a['wx:for']) return (value(a['wx:for'], scope) || []).map((item, index) => render(node, { ...scope, [a['wx:for-item'] || 'item']: item, [a['wx:for-index'] || 'index']: index }, true)).join('')
  const tag = node.tag
  if (tag === 'block') return children(node.children, scope)
  if (['glyph-image', 'view-state', 'feature-note'].includes(tag)) {
    const props = Object.fromEntries(Object.entries(a).filter(([key]) => !key.startsWith('bind')).map(([key, val]) => [key.replace(/-([a-z])/g, (_, c) => c.toUpperCase()), value(val, scope)]))
    if (tag === 'glyph-image') {
      // Read the actual initial state; otherwise !failed falsely hides valid images.
      vm.runInNewContext(read('components/glyph-image/index.js'), { Component(component) { Object.assign(props, component.data) } })
    }
    return `<div class="component-${tag}">${children(tree(`components/${tag}/index.wxml`), props)}</div>`
  }
  const htmlTag = ({ view: 'div', 'cover-view': 'div', text: 'span', image: 'img', 'scroll-view': 'div', map: 'div', progress: 'div' })[tag] || tag
  let attributes = ''
  for (const [key, val] of Object.entries(a)) {
    if (key.startsWith('wx:') || key.startsWith('bind') || key.startsWith('catch')) continue
    const v = value(val, scope)
    if (['disabled', 'loading'].includes(key)) { if (v) attributes += ` ${key}`; continue }
    if (key === 'src') { attributes += ` src="${assets(v)}"`; continue }
    attributes += ` ${key}="${escape(v)}"`
  }
  if (tag === 'image') return `<img${attributes} style="object-fit:${a.mode === 'aspectFill' ? 'cover' : 'contain'}">`
  if (tag === 'map') return `<div${attributes} style="position:relative;display:flex;align-items:center;justify-content:center;background:#e0e8df;color:#607261"><span style="max-width:65%;text-align:center;font-size:12px">原生地图占位 · 浏览器不模拟真实底图</span>${children(node.children, scope)}</div>`
  if (tag === 'progress') {
    const height = Number(a['stroke-width']) || 5, radius = Number(a['border-radius']) || height
    const track = escape(value(a.backgroundColor || '#e9ddcb', scope)), fill = escape(value(a.activeColor || '#a73529', scope))
    return `<div style="height:${height}px;border-radius:${radius}px;background:${track};overflow:hidden"><div style="height:100%;width:${Number(value(a.percent,scope)) || 0}%;background:${fill}"></div></div>`
  }
  return `<${htmlTag}${attributes}>${children(node.children, scope)}</${htmlTag}>`
}
const glyphs = ['山', '月', '花', '水', '较长的示例词名'].map((cn_name, i) => ({ id: 'fixture-' + i, cn_name, image_url: '', culture_summary: '仅用于检查布局的示例文字，不是已审核文化释义。', score_text: i ? '' : '68.2%', selected: i < 3 }))
const merchants = [1, 2, 3].map(i => ({ id: 'fixture-merchant-' + i, name: '文化商户布局示例 ' + i, image_url: '/assets/home/landscape.jpg', address: '示例地址 · 不是真实推荐', tags: ['文化体验', '手作'], displayTags: ['布局示例', '非真实商户'], distance: '' }))
const mapPoints = merchants.map((item, index) => ({ ...item, merchant_id: item.id, type_label: '文化商户', display_tags: ['布局示例', '非真实商户'], is_quest: index === 1, distance: ['450 m', '320 m', '680 m'][index] }))
const resultPreview = { ...glyphs[0], available: true, rank: 1, category_l1: '布局示例', display_tags: ['示例分类', '内容夹具'], culture_detail: '此处只检查文化正文的行距、段落和长文本排版，不是已审核文化解释。真实页面仅展示字典接口中的已发布内容；没有媒体、字形或关联商户时明确显示缺失状态。', source_ref: '仅用于离线布局测试', audio_url: '/fixture-audio.mp3', variants: [1, 2, 3].map(() => ({ image_url: '', source_ref: '布局测试占位，非东巴字形' })) }
const products = [1, 2].map(i => ({ id: 'fixture-product-' + i, name: '丽江好物布局示例 ' + i, merchant_id: merchants[0].id, image_url: i === 1 ? '/assets/home/landscape.jpg' : '', description: '商品描述仅用于排版测试，不是真实推荐商品。', price: i === 1 ? '68.00' : '129.00' }))
const fixtures = {
  home: { today: { ...glyphs[0], category_l1: '示例分类' }, merchants, todayText: '2026年9月27日 星期日' },
  result: { image: '/assets/home/landscape.jpg', result: { request_id: 'fixture-request' }, preview: resultPreview, candidates: glyphs, selected: '', comment: '', merchants: merchants.map(item => ({ ...item, display_tags: ['布局示例', '非真实商户'] })) },
  character: { item: { ...glyphs[0], category_l1: '示例分类', culture_detail: '此处仅检查长段落、字形和操作区的版面。文化说明仍来自真实接口中的已发布内容，不使用本测试文字作为业务内容。', source_ref: '布局夹具', variants: [{ image_url: '', source_ref: '示例字形来源' }] }, related: glyphs.slice(1), merchants, products },
  map: { center: { latitude: 26, longitude: 100 }, location: { latitude: 26, longitude: 100 }, scale: 15, sort: 'default', filter: 'all', selected: mapPoints[0], visiblePoints: mapPoints },
  quests: questFixture(),
  quest: questDetailFixture(),
  poster: { items: glyphs, selected: glyphs.slice(0, 3).map(g => g.id), template: 'paper' }
}
async function main() {
  fs.mkdirSync(out, { recursive: true })
  const browser = await chromium.launch({ headless: true, channel: 'msedge' })
  const report = []
  try {
    const page = await browser.newPage({ deviceScaleFactor: 1 })
    await page.route('**/*', route => route.abort())
    for (const width of (homeOnly || mapOnly || resultOnly || characterOnly || questsOnly || questOnly ? [320, 375, 390, 430] : [320, 375, 430])) {
      const height = homeOnly || mapOnly || resultOnly || characterOnly || questsOnly || questOnly ? ({ 320: 568, 375: 667, 390: 844, 430: 932 })[width] : 844
      await page.setViewportSize({ width, height })
      for (const [name, fixture] of Object.entries(fixtures)) {
        if (homeOnly && name !== 'home') continue
        if (mapOnly && name !== 'map') continue
        if (resultOnly && name !== 'result') continue
        if (characterOnly && name !== 'character') continue
        if (questsOnly && name !== 'quests') continue
        if (questOnly && name !== 'quest') continue
        const states = [['content', fixture]]
        if (name === 'quest') {
          configuredQuestFixtures().forEach((data, index) => states.push(['configured-route-' + (index + 1), data]))
          const complete = { ...fixture, completed: fixture.nodes.length, percent: 100, nodes: fixture.nodes.map(node => ({ ...node, completed: true, is_next: false })), progress: { status: 'completed', reward_pending: false } }
          states.push(
            ['guest', { ...fixture, progress: null }],
            ['reward-issued', { ...complete, reward: { title: '离线布局测试体验券' } }],
            ['reward-pending', { ...complete, progress: { ...complete.progress, reward_pending: true } }],
            ['complete-no-reward', complete],
            ['route-closed', { ...fixture, closed: true }],
            ['long-content', { ...fixture, item: { ...fixture.item, name: fixture.item.name.repeat(4), description: fixture.item.description.repeat(6) }, nodes: fixture.nodes.map(node => ({ ...node, name: '用于验证长节点名称换行的排版示例'.repeat(3) })) }],
            ['long-reward', { ...complete, reward: { title: '非常长的离线布局测试体验券名称'.repeat(6) } }],
            ['busy', { ...fixture, busy: 'both' }],
            ['hero-failed', { ...fixture, heroFailed: true }],
            ['quest-button-stress', fixture],
            ['no-nodes', { ...fixture, nodes: [] }]
          )
        }
        if (name === 'quests') {
          const long = questFixture(3, 0, { name: '验证路线长标题自然换行不会超出纸笺的测试名称'.repeat(2), area: '用于测试换行的长地区名称' })
          long.items.push({ id: 'fixture-second', name: '第二条很长的路线名称'.repeat(5) })
          long.feature.nodes.forEach(node => { node.name = '用于测试两行截断的很长任务名称'.repeat(3) })
          long.rewardTitle = '非常长的完成奖励名称'.repeat(4)
          states.push(['no-media', questFixture(3, 1, {}, { noMedia: true })])
          for (const count of [2, 4, 5, 6, 7, 8, 9, 10, 11]) states.push(['nodes-' + count, questFixture(count, 1)])
          states.push(['single-node', questFixture(1, 0)], ['twelve-stamps', questFixture(12, 4)], ['dense-route', questFixture(15, 6)], ['no-nodes', questFixture(0, 0)], ['complete', questFixture(3, 3)], ['long-content', long], ['quests-button-stress', fixture], ['reward-unavailable', { ...fixture, rewardTitle: '', rewardUnavailable: true }], ['route-closed', questFixture(3, 1, { unavailable: true })], ['detail-loading', { ...fixture, feature: null, featureLoading: true }], ['detail-error', { ...fixture, feature: null, featureError: '这条路线暂时未能加载，请稍后重试。' }])
        }
        if (name === 'character') states.push(
          ['detail-long', { ...fixture, recognitionId: 'fixture-recognition', item: { ...fixture.item, cn_name: '用于检查长词条名称的排版示例', category_l1: '用于检查换行的分类名称', category_l2: '较长的二级分类', culture_summary: '长摘要仅为离线布局检查，不是正式文化内容。'.repeat(4) } }],
          ['detail-audio-image', { ...fixture, saved: true, playing: true, item: { ...fixture.item, image_url: '/assets/marker-culture.png', audio_url: '/fixture-audio.mp3', culture_summary: '中性图标仅检查图片布局，不代表东巴字形。' }, related: fixture.related.map(item => ({ ...item, image_url: '/assets/marker-culture.png' })) }],
          ['detail-missing', { ...fixture, item: { ...fixture.item, culture_detail: '', culture_summary: '', source_ref: '', category_l1: '', category_l2: '' }, related: [], merchants: [], products: [] }],
          ['detail-button-stress', { ...fixture, item: { ...fixture.item, audio_url: '/fixture-audio.mp3' } }],
          ['association-button-stress', fixture],
          ['association-long', { ...fixture, merchants: merchants.map(item => ({ ...item, name: '用于验证商户名称换行的非常长的名称示例', address: '用于验证两行截断的很长的地址文字测试内容'.repeat(3), distance: '12.3 km' })), products: products.map(item => ({ ...item, name: '用于验证商品标题自然换行的很长的商品名称', description: 'LongUnbrokenProductDescription'.repeat(5), price: '12345678.90' })) }],
          ['association-missing-images', { ...fixture, merchants: merchants.map(item => ({ ...item, image_url: '' })), products: products.map(item => ({ ...item, image_url: '' })) }],
          ['association-empty', { ...fixture, merchants: [], products: [] }]
        )
        if (name === 'result') states.push(
          ['result-button-stress', fixture],
          ['selected', { ...fixture, selected: glyphs[0].id }],
          ['feedback', { ...fixture, feedbackOpen: true, comment: '仅测试长段反馈说明的显示，不是真实纠错反馈。' }],
          ['missing-media', { ...fixture, image: '', preview: { ...resultPreview, variants: [], audio_url: '' }, merchants: merchants.map(item => ({ ...item, image_url: '', display_tags: [] })) }],
          ['long-content', { ...fixture, preview: { ...resultPreview, cn_name: '非常长的候选词条名称布局测试', display_tags: ['较长的分类名称示例', '第二个很长的分类标签示例'], culture_detail: resultPreview.culture_detail.repeat(3) }, candidates: glyphs.map(item => ({ ...item, cn_name: '很长的候选名布局示例' })), merchants: merchants.map(item => ({ ...item, name: '用于检查文本省略的非常长的商户名称', display_tags: ['很长的商户分类标签', '布局测试'] })) }]
        )
        if (name === 'map') states.push(
          ['map-button-stress', fixture],
          ['missing-images', { ...fixture, visiblePoints: mapPoints.map(point => ({ ...point, image_url: '' })) }],
          ['location-denied', { ...fixture, location: null, locationError: '未获得位置授权', visiblePoints: mapPoints.map(point => ({ ...point, distance: '' })) }],
          ['long-content', { ...fixture, visiblePoints: mapPoints.map(point => ({ ...point, name: '用于验证小屏换行的非常长的文化商户名称布局示例', address: '超长地址仅验证排版不会横向溢出，不是真实商户数据', display_tags: ['非常长的分类标签仅供布局测试', '布局示例'] })) }],
          ['filter-empty', { ...fixture, filter: 'quest', visiblePoints: [], selected: null }]
        )
        // Neutral UI marker tests image fitting only; never represents a Dongba glyph.
        if (name === 'home') states.push(['image-present', { ...fixture, today: { ...fixture.today, cn_name: '图片布局测试', image_url: '/assets/marker-culture.png', culture_summary: '中性图标仅用于图片容器测试，不是东巴字形。' } }])
        if (name === 'home') states.push(['button-default-stress', fixture])
        if (width === 375) {
          if (name === 'result') states.push(['unknown', { ...fixture, preview: null, candidates: [], feedbackOpen: true, merchants: [] }], ['submitted', { submitted: true }], ['expired', { error: '识别已失效' }], ['loading', { ...fixture, preview: { ...glyphs[0], rank: 1, available: false, variants: [], display_tags: [] }, previewLoading: true, merchants: [] }], ['unavailable', { ...fixture, preview: { ...glyphs[0], rank: 1, available: false, variants: [], display_tags: [] }, previewError: '该词条的已发布内容暂不可用，可重试或选择其他候选。', merchants: [] }], ['favorite-error', { ...fixture, favoriteError: '收藏状态暂不可用，请重试' }])
          else states.push(['empty', { items: [], merchants: [], visiblePoints: [], filter: 'all' }], ['loading', { loading: true }], ['error', { error: '离线布局测试：服务暂时不可用' }])
          if (name === 'poster') states.push(['generated', { ...fixture, image: '/assets/lijiang-panorama.png', shareCode: false }])
          if (name === 'home') states.push(['location-denied', { ...fixture, locationError: '未获得位置授权' }], ['missing-images', { ...fixture, merchants: merchants.map(m => ({ ...m, imageFailed: true })) }], ['long-content', { ...fixture, today: { ...fixture.today, cn_name: '用于验证长词条的布局示例', category_l1: '较长的分类示例名称' }, merchants: merchants.map(m => ({ ...m, name: '用于检查省略与可点击性的非常长商户名称', displayTags: ['较长的标签内容测试', '手工体验示例', '文创礼品示例'] })) }])
        }
        for (const [state, data] of states) {
          const css = cssForBrowser([read('app.wxss'), read(`pages/${name}/index.wxss`), ...['feature-note','view-state','glyph-image'].map(c => read(`components/${c}/index.wxss`))].join('\n'), width)
          const defaults = { loading: false, error: '', image: '', items: [], comment: '', selected: [], candidates: [], merchants: [], products: [], related: [], visiblePoints: [], scale: 15, sort: 'default', filter: 'all', satellite: false, questError: '', locationError: '', result: null, preview: null, previewLoading: false, previewError: '', merchantsLoading: false, merchantsError: '', saved: false, favoriteBusy: false, favoriteLoading: false, favoriteError: '', playing: false, feedbackOpen: false, submitted: false, busy: false, attachImage: false }
          const heroTop = width >= 390 ? 48 : 24
          const bottom = width >= 390 ? 34 : 0
          const chrome = name === 'home' ? `<div class="preview-status" aria-hidden="true">9:41</div><div class="preview-capsule" aria-hidden="true">•••<span>◉</span></div><nav class="preview-tabbar" aria-label="模拟原生导航">${appConfig.tabBar.list.map((tab, i) => `<div style="color:${i ? appConfig.tabBar.color : appConfig.tabBar.selectedColor}"><img src="${assets('/' + (i ? tab.iconPath : tab.selectedIconPath))}"><span>${tab.text}</span></div>`).join('')}</nav>` : ''
          const chromeCss = name === 'home' ? `body{padding-bottom:${49+bottom}px}.home-page{min-height:calc(100vh - ${49+bottom}px)}.preview-status{position:absolute;top:6px;left:21px;color:#111;font:600 12px Arial;z-index:8}.preview-capsule{position:absolute;top:${heroTop}px;right:8px;width:87px;height:32px;border:1px solid #ffffff55;background:#ffffffb3;border-radius:20px;display:flex;align-items:center;justify-content:space-evenly;font:700 17px Arial;z-index:8}.preview-capsule span{border-left:1px solid #d3dce3;padding-left:12px}.preview-tabbar{position:fixed;bottom:0;left:0;width:100%;height:${49+bottom}px;padding-bottom:${bottom}px;display:flex;background:white;border-top:1px solid #edeef0;z-index:9}.preview-tabbar>div{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;font-size:10px;line-height:14px}.preview-tabbar img{width:26px;height:26px}${bottom ? '.preview-tabbar::after{content:"";position:absolute;bottom:8px;left:35%;width:30%;height:4px;background:#111;border-radius:8px}' : ''}` : ''
          await page.setContent(`<!doctype html><html lang="zh-CN"><meta charset="UTF-8"><style>body{margin:0}button{font-family:inherit;border:0;cursor:pointer}img{max-width:100%}textarea{font-family:inherit}div,span,button{box-sizing:border-box}div[scroll-x]{overflow-x:auto}.component-glyph-image{height:100%;width:100%}${css}${chromeCss}</style><body>${children(tree(`pages/${name}/index.wxml`), { ...defaults, heroTop, locating: false, location: null, ...data })}${chrome}</body></html>`)
          // Native tab height includes its safe-area padding; don't count it twice.
          await page.addStyleTag({ content: '.preview-tabbar{box-sizing:border-box}' })
          if (name === 'quests') {
            await page.evaluate(({ tabs, top }) => {
              const chrome = document.createElement('aside')
              chrome.innerHTML = '<div class="quest-preview-status">9:41</div><div class="quest-preview-capsule">•••<span>◉</span></div><nav class="quest-preview-tabs">' + tabs.map((tab, index) => '<div style="color:' + (index === 1 ? '#ad3425' : '#737371') + '"><img src="' + tab.image + '"><span>' + tab.text + '</span></div>').join('') + '</nav>'
              document.body.append(chrome)
              document.querySelector('.quest-preview-capsule').style.top = top + 'px'
            }, { tabs: appConfig.tabBar.list.map((tab, index) => ({ text: tab.text, image: assets('/' + (index === 1 ? tab.selectedIconPath : tab.iconPath)) })), top: heroTop })
            await page.addStyleTag({ content: `body{padding-bottom:${49 + bottom}px}.quest-preview-status{position:absolute;top:5px;left:21px;font:600 12px Arial;color:white}.quest-preview-capsule{position:absolute;right:8px;width:87px;height:32px;display:flex;align-items:center;justify-content:space-evenly;background:#ffffffd9;border-radius:20px;font:700 17px Arial}.quest-preview-capsule span{padding-left:12px;border-left:1px solid #aaa}.quest-preview-tabs{position:fixed;bottom:0;left:0;right:0;display:flex;height:${49 + bottom}px;padding-bottom:${bottom}px;box-sizing:border-box;background:white;border-top:1px solid #eee;z-index:9}.quest-preview-tabs>div{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:10px;line-height:14px}.quest-preview-tabs img{width:26px;height:26px}` })
          }
          if (state === 'quests-button-stress') await page.addStyleTag({ content: 'button:not([size="mini"]){width:184px;min-width:184px;margin-left:auto;margin-right:auto}' })
          if (name === 'map') {
            // Approximate the existing native navigation and tab bar, not app-owned chrome.
            await page.evaluate(({ tabs, title, bottom }) => {
              const nav = document.createElement('header'); nav.className = 'preview-map-nav'; nav.innerHTML = '<div>9:41</div><strong>' + title + '</strong>'; document.body.prepend(nav)
              const bar = document.createElement('nav'); bar.className = 'preview-map-tabbar'; bar.innerHTML = tabs.map((tab, i) => '<span style="color:' + (i === 2 ? '#bc2d19' : '#737371') + '">' + tab.text + '</span>').join(''); bar.style.paddingBottom = bottom + 'px'; document.body.append(bar)
            }, { tabs: appConfig.tabBar.list, title: '东巴地图', bottom })
            await page.addStyleTag({ content: `body{padding-bottom:${49 + bottom}px}.preview-map-nav{background:#edf2f4;height:68px;padding:6px 20px;color:#263038}.preview-map-nav div{font-size:12px;line-height:20px}.preview-map-nav strong{display:block;text-align:center;line-height:36px;font-size:16px}.preview-map-tabbar{position:fixed;bottom:0;left:0;right:0;display:flex;align-items:center;justify-content:space-around;height:${49 + bottom}px;box-sizing:border-box;background:white;border-top:1px solid #eee;z-index:9;font-size:12px}` })
          }
          if (name === 'quest') {
            await page.evaluate(() => { const nav = document.createElement('header'); nav.className = 'preview-detail-nav'; nav.innerHTML = '<div>9:41</div><strong>‹　寻迹路线</strong><span>•••　◉</span>'; document.body.prepend(nav) })
            await page.addStyleTag({ content: '.preview-detail-nav{position:relative;height:68px;padding:6px 20px;background:#f6f8f6;color:#263d35;box-sizing:border-box}.preview-detail-nav div{font:600 12px/20px sans-serif}.preview-detail-nav strong{display:block;font:600 16px/36px sans-serif}.preview-detail-nav>span{position:absolute;right:12px;bottom:8px;border:1px solid #dde4df;border-radius:20px;padding:4px 10px;font-size:14px}.route-sheet{padding-bottom:calc(22px + ' + bottom + 'px)}' })
            if (state === 'quest-button-stress') await page.addStyleTag({ content: 'button[size="mini"]{display:inline-block;margin-left:auto;margin-right:auto;padding:0 1.32em;font-size:13px;line-height:2.3}button:not([size="mini"]){width:184px;min-width:184px;margin:auto}' })
          }
          if (name === 'result') {
            await page.evaluate(() => { const nav = document.createElement('header'); nav.className = 'preview-result-nav'; nav.innerHTML = '<div>9:41</div><strong>‹　识别结果</strong>'; document.body.prepend(nav) })
            await page.addStyleTag({ content: `.preview-result-nav{height:68px;padding:6px 20px;background:#edf2f4;color:#263038}.preview-result-nav div{font-size:12px;line-height:20px}.preview-result-nav strong{display:block;line-height:36px;font-size:16px}.result-action-bar{padding-bottom:calc(${16 * width / 750}px + ${bottom}px)}.result-page{padding-bottom:calc(${170 * width / 750}px + ${bottom}px)}` })
          }
          if (state === 'map-button-stress' || state === 'result-button-stress') await page.addStyleTag({ content: 'button[size="mini"]{display:inline-block;margin-left:auto;margin-right:auto;padding:0 1.32em;font-size:13px;line-height:2.3}button:not([size="mini"]){width:184px;min-width:184px;margin:auto}' })
          if (state === 'association-button-stress') {
            await page.addStyleTag({ content: '.association-section button:not([size="mini"]){width:184px;min-width:184px;margin-left:auto;margin-right:auto}.association-section button[size="mini"]{display:inline-block;margin-left:auto;margin-right:auto;padding:0 1.32em;font-size:13px;line-height:2.3}' })
            const negativeControl = await page.locator('.merchant-row').first().evaluate(button => {
              button.removeAttribute('size')
              const style = getComputedStyle(button.parentElement)
              const available = button.parentElement.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)
              const oldWidth = button.getBoundingClientRect().width
              button.setAttribute('size', 'mini')
              return { oldWidth, available }
            })
            assert.ok(negativeControl.oldWidth < negativeControl.available - 10, 'Negative control must expose the native narrow-row regression')
          }
          if (name === 'character') {
            await page.evaluate(() => { const nav = document.createElement('header'); nav.className = 'preview-character-nav'; nav.innerHTML = '<div>9:41</div><strong>‹　东巴字详情</strong>'; document.body.prepend(nav) })
            await page.addStyleTag({ content: `.preview-character-nav{height:68px;padding:6px 20px;background:#edf2f4;color:#263038}.preview-character-nav div{font-size:12px;line-height:20px}.preview-character-nav strong{display:block;line-height:36px;font-size:16px}.character-page .character-actions{padding-bottom:calc(${16 * width / 750}px + ${bottom}px)}.character-page{padding-bottom:calc(${180 * width / 750}px + ${bottom}px)}` })
            if (state === 'detail-button-stress') await page.addStyleTag({ content: 'button:not([size="mini"]){width:184px;min-width:184px;margin-left:auto;margin-right:auto}' })
          }
          let buttonRegression = null
          if (state === 'button-default-stress') {
            // Simulated native-button defaults, not a real WeChat runtime stylesheet.
            // The old wrapper must fail this control; the layout view must ignore it.
            await page.addStyleTag({ content: 'button.today:not([size="mini"]),button.daily-detail:not([size="mini"]),button.more-button:not([size="mini"]){width:184px;min-width:184px;max-width:none;margin-left:auto;margin-right:auto}button.daily-detail[size="mini"],button.more-button[size="mini"]{display:inline-block;padding:0 1.32em;line-height:2.3;font-size:13px}' })
            buttonRegression = await page.evaluate(() => {
              const layout = document.querySelector('.today')
              const button = document.createElement('button')
              button.className = layout.className
              button.innerHTML = layout.innerHTML
              layout.replaceWith(button)
              const header = document.querySelector('.daily-header').getBoundingClientRect()
              const oldLeft = button.querySelector('.daily-glyph-frame').getBoundingClientRect().left
              const oldWidth = button.getBoundingClientRect().width
              button.replaceWith(layout)
              return { simulated: true, oldWidth, headerWidth: header.width, oldLeftOffset: oldLeft - header.left }
            })
            assert.ok(buttonRegression.oldLeftOffset > 1, 'Control must reproduce the old centered button row')
          }
          await page.evaluate(() => document.fonts.ready)
          const metrics = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth, buttons: Array.from(document.querySelectorAll('button')).filter(b => b.getBoundingClientRect().height > 0).map(b => ({ className: b.className, text: b.textContent.trim().slice(0,30), height: Math.round(b.getBoundingClientRect().height) })) }))
          if (buttonRegression) metrics.buttonRegression = buttonRegression
          await page.screenshot({ path: path.join(out, `${name}-${state}-${width}.png`), fullPage: true })
          if (name === 'quests') {
            await page.screenshot({ path: path.join(out, `${name}-${state}-${width}-viewport.png`) })
            const layout = await page.evaluate(() => {
              const rect = selector => document.querySelector(selector)?.getBoundingClientRect().toJSON()
              const stamps = Array.from(document.querySelectorAll('.orbit-node')).map(element => element.getBoundingClientRect().toJSON())
              const overlap = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1
              return { orbit: rect('.stamp-orbit'), center: rect('.orbit-center'), stamps, overlaps: stamps.some((a, i) => stamps.some((b, j) => i !== j && overlap(a, b))), grid: !!document.querySelector('.is-grid'), nav: rect('.quest-nav > text') || rect('.quest-nav > span'), capsule: rect('.quest-preview-capsule'), missingImages: [...document.images].filter(image => !image.complete || !image.naturalWidth).length, cards: [...document.querySelectorAll('.discovery-cards > div')].map(element => element.getBoundingClientRect().toJSON()) }
            })
            assert.equal(layout.missingImages, 0, 'Quest assets must load offline')
            assert.equal(layout.overlaps, false, `Quest stamp targets overlap at ${width}/${state}`)
            assert.equal(layout.stamps.length, data.feature?.nodes.length || 0)
            assert.ok(layout.nav.right <= layout.capsule.left, 'Quest title must avoid the WeChat capsule')
            if (layout.orbit) {
              assert.ok(layout.stamps.every(stamp => stamp.left >= layout.orbit.left - 1 && stamp.right <= layout.orbit.right + 1), 'Stamp targets must stay inside the paper')
              assert.ok(layout.stamps.every(stamp => stamp.width >= 44 && stamp.height >= 44), 'Stamp targets must be at least 44px')
            }
            assert.ok(layout.cards.every(card => card.width > 90 && card.right <= width), 'Next target and reward cards must fit side by side')
            for (const selector of ['.journey-tab', '.album-link', '.journey-primary', '.next-link', '.reward-link', '.map-link']) {
              if (!await page.locator(selector).count()) continue
              const target = page.locator(selector).first()
              // Native tabs live outside the mini-program viewport. Center the
              // target above our fixed HTML approximation before hit testing.
              await target.evaluate(button => button.scrollIntoView({ block: 'center', inline: 'nearest' }))
              const hit = await target.evaluate(button => { const r = button.getBoundingClientRect(); return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)?.closest('button') === button })
              assert.ok(hit, `Quest action ${selector} must not be covered at ${width}/${state}`)
            }
            metrics.quests = layout
            await page.evaluate(() => window.scrollTo(0, 0))
          }
          if (name === 'character') {
            assert.equal(await page.locator('.variants,.variant-track').count(), 0, 'D-064 removes the detail writing card, including records with variants')
            if (data.item && !data.loading) {
              const footer = await page.locator('.character-actions button').evaluateAll(buttons => buttons.map(button => {
                const r = button.getBoundingClientRect()
                return { width: r.width, height: r.height, fits: button.scrollWidth <= button.clientWidth + 1, hit: document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)?.closest('button') === button }
              }))
              assert.equal(footer.length, 3)
              assert.ok(footer.every(button => button.width >= 44 && button.height >= 44 && button.fits && button.hit), `D-064 footer accessible: ${JSON.stringify(footer)}`)
              assert.equal(await page.locator('.related-word').count(), (data.related || []).length)
              assert.equal(await page.locator('.audio').count(), data.item.audio_url ? 1 : 0)
              assert.equal(await page.locator('.media-unavailable').count(), data.item.audio_url ? 0 : 1)
              const identity = await page.locator('.character-identity').evaluate(element => ({ scroll: element.scrollWidth, width: element.clientWidth }))
              assert.ok(identity.scroll <= identity.width + 2, 'D-064 identity and long word fit the phone width')
            }
            const associationMetrics = await page.evaluate(() => {
              const rect = element => element.getBoundingClientRect().toJSON()
              return Array.from(document.querySelectorAll('.association-section')).map(section => {
                const style = getComputedStyle(section), r = rect(section)
                const left = r.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft)
                const right = r.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight)
                const heading = section.querySelector('.section-title'), more = section.querySelector('.association-more')
                return { className: section.className, left, right, heading: rect(heading), headingOverflow: heading.scrollWidth > heading.clientWidth + 1, more: more ? rect(more) : null,
                  rows: Array.from(section.querySelectorAll('.merchant-row')).map(row => ({ row: rect(row), image: rect(row.querySelector('.thumb')), copy: rect(row.querySelector('.association-copy')), arrow: rect(row.querySelector('.chevron')), alignment: getComputedStyle(row).textAlign, names: Array.from(row.querySelectorAll('.item-title,.association-description,.price')).map(text => ({ width: text.clientWidth, scroll: text.scrollWidth, left: rect(text).left, right: rect(text).right })) })) }
              })
            })
            for (const section of associationMetrics) {
              assert.ok(!section.headingOverflow, 'Association heading must fit')
              if (section.more) {
                assert.ok(section.heading.right < section.more.left, 'Heading and All action must not overlap')
                assert.ok(section.more.width >= 64 && section.more.width <= 80 && section.more.height >= 44, 'All action must stay compact but tappable')
              }
              for (const row of section.rows) {
                assert.ok(Math.abs(row.row.left - section.left) < 1 && Math.abs(row.row.right - section.right) < 1, 'Association row must fill and align with card content, not center at a native fixed width')
                assert.equal(row.alignment, 'left', 'Association text must remain left aligned')
                assert.ok(Math.abs(row.image.width - 128 * width / 750) < 1 && Math.abs(row.image.height - row.image.width) < 1, 'Image must remain fixed and square')
                assert.ok(row.image.right < row.copy.left && row.copy.right < row.arrow.left && row.arrow.right <= section.right + 1, 'Image, content and arrow must not squeeze or overlap')
                assert.ok(row.copy.width >= 120, 'Copy must have useful width on 320px screens')
                assert.ok(row.names.every(text => text.scroll <= text.width + 1 && text.left >= row.copy.left - 1 && text.right <= row.copy.right + 1), 'Long titles, descriptions and prices must remain in the copy column')
              }
            }
            for (const target of await page.locator('.association-more,.merchant-row').all()) {
              await target.evaluate(button => button.scrollIntoView({ block: 'center', inline: 'nearest' }))
              const hit = await target.evaluate(button => {
                const r = button.getBoundingClientRect()
                return { width: r.width, height: r.height, points: [[r.width / 2, r.height / 2], [3, r.height / 2], [r.width - 3, r.height / 2], [r.width / 2, 3], [r.width / 2, r.height - 3]].map(([x, y]) => button.contains(document.elementFromPoint(r.left + x, r.top + y))) }
              })
              assert.ok(hit.height >= 44 && hit.points.every(Boolean), `Association action must remain reachable: ${JSON.stringify(hit)}`)
            }
            if (state === 'content' || state === 'association-long' || state === 'association-button-stress') {
              for (const selector of ['.merchant-section', '.product-section']) {
                if (!await page.locator(selector).count()) continue
                await page.locator(selector).evaluate(section => section.scrollIntoView({ block: 'start' }))
                await page.screenshot({ path: path.join(out, `${name}-${state}-${width}-${selector.slice(1)}.png`) })
              }
            }
            await page.evaluate(() => window.scrollTo(0, 0))
            metrics.associations = associationMetrics
          }
          if (name === 'result') {
            await page.screenshot({ path: path.join(out, `${name}-${state}-${width}-viewport.png`) })
            const resultMetrics = await page.evaluate(() => {
              const rect = selector => document.querySelector(selector)?.getBoundingClientRect().toJSON()
              return { photo: rect('.hero-photo'), copy: rect('.hero-copy'), bar: rect('.result-action-bar'), comparison: rect('.comparison-row'), previewOnly: !document.querySelector('.candidate.is-selected'), headings: Array.from(document.querySelectorAll('.result-heading')).map(element => ({ width: element.clientWidth, scroll: element.scrollWidth })) }
            })
            if (resultMetrics.photo) {
              assert.ok(resultMetrics.photo.right < resultMetrics.copy.left, 'Photo stays left of the candidate introduction')
              assert.ok(resultMetrics.copy.right <= width, 'Candidate introduction stays inside viewport')
            }
            assert.ok(resultMetrics.headings.every(value => value.scroll <= value.width + 1), `Result section titles must not overflow: ${JSON.stringify(resultMetrics.headings)}`)
            resultMetrics.hitTargets = []
            for (const selector of ['.hero-save', '.hero-audio', '.result-more', '.feedback-toggle', '.retake-action', '.confirm-action', '.review-action', '.candidate:last-child']) {
              const target = page.locator(selector)
              if (!await target.count() || await target.isDisabled()) continue
              await target.evaluate(button => button.scrollIntoView({ block: 'center', inline: 'nearest' }))
              const hit = await target.evaluate(button => {
                const r = button.getBoundingClientRect()
                return { selector: button.className, width: r.width, height: r.height, scroll: button.scrollWidth, client: button.clientWidth, points: [[r.width / 2, r.height / 2], [3, r.height / 2], [r.width - 3, r.height / 2], [r.width / 2, 3], [r.width / 2, r.height - 3]].map(([x, y]) => button.contains(document.elementFromPoint(r.left + x, r.top + y))) }
              })
              assert.ok(hit.width >= 44 && hit.height >= 44, `Result touch target needs 44px: ${JSON.stringify(hit)}`)
              assert.ok(hit.scroll <= hit.client + 1, `Result button text must fit: ${JSON.stringify(hit)}`)
              assert.ok(hit.points.every(Boolean), `Result action must not be obstructed or clipped: ${JSON.stringify(hit)}`)
              resultMetrics.hitTargets.push(hit)
            }
            if (state === 'content') {
              await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
              await page.screenshot({ path: path.join(out, `${name}-${state}-${width}-bottom.png`) })
            }
            await page.evaluate(() => window.scrollTo(0, 0))
            metrics.result = resultMetrics
          }
          if (name === 'map') {
            await page.screenshot({ path: path.join(out, `${name}-${state}-${width}-viewport.png`) })
            const layout = await page.evaluate(() => {
              const rect = element => element.getBoundingClientRect().toJSON()
              return { map: document.querySelector('.map') ? rect(document.querySelector('.map')) : null,
                cards: [...document.querySelectorAll('.place-card')].map(card => ({ card: rect(card), photo: rect(card.querySelector('.place-photo')), copy: rect(card.querySelector('.place-copy')), name: rect(card.querySelector('.place-name')), address: rect(card.querySelector('.place-address')), navigate: rect(card.querySelector('.place-navigate')) })),
                images: [...document.images].filter(image => !image.complete || !image.naturalWidth).map(image => image.className),
                filters: [...document.querySelectorAll('.map-tab')].map(rect) }
            })
            assert.equal(layout.images.length, 0, 'Map preview assets must load')
            if (layout.map) assert.equal(layout.map.width, width, 'Native map area must fill the screen width')
            assert.equal(layout.filters.length, 4)
            assert.equal(await page.locator('.map-brand').count(), 0, 'Map must not restore the removed top-right wordmark')
            assert.ok(layout.filters.every(rect => rect.height === 44 && rect.width >= 44), 'Category targets remain compact and tappable')
            for (const [selector, height] of [['.map-tab-label', 36], ['.navigate-pill', 34]]) {
              const sizes = await page.locator(selector).evaluateAll(elements => elements.map(element => ({ height: element.getBoundingClientRect().height, parentHeight: element.parentElement.getBoundingClientRect().height })))
              assert.ok(sizes.every(size => size.height === height && size.parentHeight === 44), 'Visible capsules stay smaller than their touch targets')
            }
            for (const card of layout.cards) {
              assert.ok(card.copy.left > card.photo.right, 'Point description must be right of the photo')
              assert.ok(Math.abs(card.name.left - card.address.left) < 1, 'Name and address share a left edge')
              assert.ok(card.copy.right <= card.card.right && card.navigate.right <= card.card.right, 'Content must remain within its card')
              assert.ok(card.navigate.height === 44 && card.navigate.width >= 76, 'Navigation keeps a compact 44px tap height')
              assert.ok(card.navigate.width <= Math.max(76, 164 * width / 750) + 1, 'Navigation must not expand into an oversized pill')
            }
            layout.hitTargets = []
            for (const selector of ['.map-tab', '.sort-tab', '.map-tool', '.map-zoom', '.place-navigate', '.place-detail', '.empty-locate']) {
              const targets = page.locator(selector)
              for (let i = 0; i < await targets.count(); i++) {
                const target = targets.nth(i)
                await target.evaluate(element => element.scrollIntoView({ block: 'center', inline: 'nearest' }))
                const hit = await target.evaluate(element => {
                  const r = element.getBoundingClientRect()
                  const positions = [[r.width / 2, r.height / 2], [3, r.height / 2], [r.width - 3, r.height / 2], [r.width / 2, 3], [r.width / 2, r.height - 3]]
                  return { width: r.width, height: r.height, points: positions.map(([x,y]) => { const top = document.elementFromPoint(r.left + x, r.top + y); return top === element || element.contains(top) }) }
                })
                assert.ok(hit.width >= 44 && hit.height >= 44, `${name}/${state}/${width}/${selector}: tap target too small`)
                assert.ok(hit.height <= (selector === '.map-tool' ? 48 : 44), `${name}/${state}/${width}/${selector}: oversized control`)
                if (selector === '.map-tool' || selector === '.map-zoom') assert.equal(hit.width, 44, 'Map tools must have a compact bounded width')
                assert.ok(hit.points.every(Boolean), `${name}/${state}/${width}/${selector}: control blocked: ${JSON.stringify(hit)}`)
                layout.hitTargets.push({ selector, ...hit })
              }
            }
            metrics.map = layout
            await page.evaluate(() => window.scrollTo(0, 0))
          }
          if (name === 'home') {
            await page.screenshot({ path: path.join(out, `${name}-${state}-${width}-viewport.png`) })
            const homeMetrics = await page.evaluate(() => {
              const rect = selector => document.querySelector(selector)?.getBoundingClientRect().toJSON()
              const frame = document.querySelector('.daily-glyph-frame')
              const detail = document.querySelector('.daily-detail')
              const detailPill = detail ? getComputedStyle(detail, '::before') : null
              const image = document.querySelector('.daily-glyph .glyph')
              const daily = frame ? { frame: rect('.daily-glyph-frame'), header: rect('.daily-header'), copy: rect('.daily-copy'), name: rect('.daily-name'), summary: rect('.daily-summary'), today: rect('.today'), background: getComputedStyle(frame).backgroundColor, radius: parseFloat(getComputedStyle(frame).borderTopLeftRadius), blend: getComputedStyle(document.querySelector('.daily-glyph')).mixBlendMode, alignment: getComputedStyle(document.querySelector('.daily-summary')).textAlign, imageFit: image ? getComputedStyle(image).objectFit : null } : null
              return { brand: rect('.brand-row'), capsule: rect('.preview-capsule'), landscape: rect('.home-landscape'), quick: rect('.quick-nav'), tab: rect('.preview-tabbar'), more: rect('.more-button'), detail: detail ? { box: rect('.daily-detail'), heading: rect('.daily-heading'), size: detail.getAttribute('size'), pillWidth: parseFloat(detailPill.width), pillHeight: parseFloat(detailPill.height), pillRight: detail.getBoundingClientRect().right - parseFloat(detailPill.right), padding: getComputedStyle(detail).paddingLeft, display: getComputedStyle(detail).display } : null, daily, cards: [...document.querySelectorAll('.merchant-card')].map(e => e.getBoundingClientRect().toJSON()), missingAssets: [...document.images].filter(i => !i.complete || !i.naturalWidth).map(i => i.className) }
            })
            assert.equal(homeMetrics.landscape.width, width, 'Home background must be full bleed')
            assert.equal(homeMetrics.tab.height, 49 + bottom, 'Mock tab safe area must not be counted twice')
            assert.ok(homeMetrics.brand.right < homeMetrics.capsule.left, 'Brand overlaps native capsule')
            assert.equal(homeMetrics.missingAssets.length, 0, 'Local preview images must load')
            if (homeMetrics.daily) {
              const daily = homeMetrics.daily
              const detail = homeMetrics.detail
              const more = homeMetrics.more
              assert.equal(detail.size, 'mini', 'Detail must opt out of the wide native default')
              assert.equal(detail.display, 'flex', 'Mini-button defaults must not override the compact layout')
              assert.equal(parseFloat(detail.padding), 0, 'Native mini-button padding must not stretch the pill')
              assert.ok(Math.abs(detail.box.width - 148 * width / 750) < 1, 'Detail touch area must have a bounded compact width')
              assert.ok(Math.abs(detail.box.height - 52) < 1, 'Detail touch area must remain easy to tap')
              assert.ok(Math.abs(detail.pillWidth - 136 * width / 750) < 1, 'Visible detail pill must match the reference proportions')
              assert.ok(Math.abs(detail.pillHeight - 42 * width / 750) < 1, 'Visible detail pill must remain comfortably visible')
              assert.ok(Math.abs(detail.pillRight - daily.header.right) < 1, 'Detail pill must align to the header right edge')
              assert.ok(detail.box.left > detail.heading.right, 'Detail must not overlap the heading')
              assert.ok(more.height >= 52, 'More button must keep a generous touch height')
              assert.ok(Math.abs(more.width - 148 * width / 750) < 1, 'More button must keep a generous but bounded touch width')
              assert.ok(Math.abs(daily.today.width - daily.header.width) < 1, 'Today content must fill the same width as the header')
              assert.ok(Math.abs(daily.frame.width - daily.frame.height) < 1, 'Glyph frame must stay square')
              assert.equal(daily.background, 'rgb(255, 255, 255)', 'Glyph frame must stay white')
              assert.ok(daily.radius >= 8, 'Glyph frame needs visible rounded corners')
              assert.equal(daily.blend, 'normal', 'Paper must not tint the glyph image')
              assert.ok(Math.abs(daily.frame.left - daily.header.left) < 1, 'Glyph frame must align with the heading, not center in the card')
              assert.ok(daily.copy.left > daily.frame.right, 'Introduction must remain to the right of the image')
              assert.ok(Math.abs(daily.name.left - daily.summary.left) < 1, 'Name and introduction must share their left edge')
              assert.equal(daily.alignment, 'left', 'Introduction must be explicitly left aligned')
              assert.ok(daily.copy.right <= daily.today.right + 1, 'Long introductions must remain inside the card')
              if (state === 'image-present') assert.equal(daily.imageFit, 'contain', 'Glyph must not stretch or crop')
            }
            if (homeMetrics.cards.length) assert.ok(homeMetrics.cards[1].right < width && homeMetrics.cards[2].left < width, 'Show two cards and part of a third')
            homeMetrics.hitTargets = []
            // Inspect real hit testing at the edges, not only CSS size values.
            for (const selector of ['.daily-detail', '.more-button']) {
              const target = page.locator(selector)
              if (!await target.count()) continue
              await target.evaluate(button => button.scrollIntoView({ block: 'center', inline: 'nearest' }))
              const hit = await target.evaluate(button => {
                const r = button.getBoundingClientRect()
                const offsets = [[3, 3], [r.width - 3, 3], [3, r.height - 3], [r.width - 3, r.height - 3], [r.width / 2, r.height / 2]]
                const elements = offsets.map(([x, y]) => document.elementFromPoint(r.left + x, r.top + y))
                return { className: button.className, width: r.width, height: r.height, points: elements.map(element => element?.closest('button') === button), blockers: elements.map(element => element?.className || element?.tagName), scrollWidth: button.scrollWidth, clientWidth: button.clientWidth }
              })
              assert.ok(hit.points.every(Boolean), `${name}/${state}/${width}/${selector}: expanded touch area must not be covered or clipped: ${JSON.stringify(hit)}`)
              assert.ok(hit.height >= 52 && hit.width >= 63, `${selector}: expanded target must work at the smallest phone width`)
              assert.ok(hit.scrollWidth <= hit.clientWidth + 1, `${selector}: text must fit inside its touch area`)
              homeMetrics.hitTargets.push(hit)
            }
            await page.evaluate(() => window.scrollTo(0, 0))
            metrics.home = homeMetrics
          }
          if (metrics.scroll > width + 1) console.log(await page.evaluate(() => Array.from(document.querySelectorAll('*')).filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('[scroll-x]')).map(e => ({ tag: e.tagName, class: e.className, right: e.getBoundingClientRect().right }))))
          assert.ok(metrics.scroll <= width + 1, `${name}/${state}/${width} horizontal overflow: ${metrics.scroll}`)
          assert.ok(metrics.buttons.every(b => b.height >= 44), `${name}/${state}/${width}: undersized touch target: ${JSON.stringify(metrics.buttons.filter(b => b.height < 44))}`)
          if (name === 'quest') {
            await page.screenshot({ path: path.join(out, `${name}-${state}-${width}-viewport.png`) })
            const body = await page.locator('body').innerText()
            assert.doesNotMatch(body, /完成全部节点|查看任务地点|导航至任务地点|个节点/)
            const locationCounts = await page.locator('.node').evaluateAll(nodes => nodes.map(node => node.querySelectorAll('button.location-button').length))
            assert.ok(locationCounts.every(count => count <= 1), 'Each node exposes at most one location action')
            if (data.item && !data.loading) {
              assert.deepEqual(locationCounts, data.nodes.map(node => node.poi_id || node.merchant_id ? 1 : 0))
              assert.equal(await page.locator('.node .tag').count(), 0)
              assert.equal(await page.locator('.node-button').count(), data.nodes.length)
              assert.equal(await page.locator('.node.is-next').count(), data.progress && !data.closed ? data.nodes.filter(node => node.is_next).length : 0)
              const layout = await page.locator('.node').evaluateAll(nodes => nodes.map(node => {
                const button = node.querySelector('.node-button'), location = node.querySelector('.location-button')
                return { width: node.getBoundingClientRect().width, button: button.getBoundingClientRect().toJSON(), location: location && location.getBoundingClientRect().toJSON(), background: getComputedStyle(button).backgroundColor }
              }))
              assert.ok(layout.filter(node => node.background === 'rgb(164, 53, 42)').length <= 1, 'At most one high-emphasis node action')
              for (const node of layout) {
                assert.ok(node.button.width < node.width * .8, 'Task actions must not become full-width banners')
                if (node.location) {
                  assert.ok(node.location.width >= 44, 'Location tap area is at least 44px')
                  assert.ok(Math.abs(node.button.top - node.location.top) < 2, 'Navigation and task action share one row')
                }
              }
              metrics.questDetail = layout
              if (data.reward) assert.ok(body.includes(data.reward.title))
              if (data.progress && data.progress.reward_pending) assert.ok(body.includes('重试领取奖励'))
            }
          }
          report.push({ page: name, state, ...metrics })
        }
      }
    }
    fs.writeFileSync(path.join(out, homeOnly ? 'home-report.json' : mapOnly ? 'map-report.json' : resultOnly ? 'result-report.json' : characterOnly ? 'character-report.json' : questsOnly ? 'quests-report.json' : questOnly ? 'quest-report.json' : 'report.json'), JSON.stringify({ limitation: 'Offline Chromium approximation only. Chrome/tab bar and all content are fixtures, not WeChat/device, API, map or recognition acceptance.', checks: report }, null, 2))
    console.log(`PASS: ${report.length} offline layout cases; screenshots: runtime/miniprogram-visual/`)
  } finally { await browser.close() }
}
module.exports = { cssForBrowser, children, tree, assets, read }
if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1 })
