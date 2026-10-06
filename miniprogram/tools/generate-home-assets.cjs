/** DESIGN-01: reproducible local vector artwork, not generated cultural content.
 * Run: node miniprogram/tools/generate-home-assets.cjs
 * Requires web's Playwright/Edge and Windows STXINGKA.TTF for the raster wordmark.
 * The font is read locally for rasterization only; no font file is distributed.
 */
const fs = require('node:fs')
const path = require('node:path')
const { createRequire } = require('node:module')
const root = path.resolve(__dirname, '../..')
const { chromium } = createRequire(path.join(root, 'web/package.json'))('@playwright/test')
const gray = '#737371', red = '#bc2d19'
const outline = (body, color) => `<g fill="none" stroke="${color}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">${body}</g>`
const pin = color => `<path fill="${color}" fill-rule="evenodd" d="M32 4C18 4 10 14 10 26c0 15 22 35 22 35s22-20 22-35C54 14 46 4 32 4Zm0 13a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z"/>`
const map = '<path d="m6 14 17-7 18 8 17-7v42l-17 7-18-8-17 7Z"/><path d="M23 7v42M41 15v42"/>'
const stamp = '<path d="M15 45c0-10 12-8 12-16 0-5-5-7-5-14a10 10 0 0 1 20 0c0 7-5 9-5 14 0 8 12 6 12 16Z"/><path d="M13 51h38v7H13Z"/>'
const user = '<circle cx="32" cy="18" r="12"/><path d="M7 58c0-15 9-23 25-23s25 8 25 23"/>'
const home = '<path d="m8 28 24-21 24 21v29H40V39H24v18H8Z"/>'
const homeIcons = {
  camera: `<defs><mask id="lens"><rect width="64" height="64" fill="white"/><circle cx="32" cy="35" r="13" fill="black"/><circle cx="32" cy="35" r="8.5" fill="white"/></mask></defs><path fill="white" mask="url(#lens)" d="M10 16h10l4-7h16l4 7h10a8 8 0 0 1 8 8v28a8 8 0 0 1-8 8H10a8 8 0 0 1-8-8V24a8 8 0 0 1 8-8Z"/>`,
  map: '<defs><linearGradient id="m"><stop stop-color="#18b7ab"/><stop offset="1" stop-color="#087d7d"/></linearGradient></defs><path fill="url(#m)" d="m3 13 19-8 20 8 19-8v47l-19 8-20-8-19 8Z"/><path d="M22 5v47M42 13v47M3 35l19-8 20 8 19-8" fill="none" stroke="#c2f2e8" stroke-width="1.8"/>',
  scroll: '<path fill="#d68130" d="M10 10h43v44H10Z"/><path d="M11 7v50M53 7v50" stroke="#bb6019" stroke-width="8" stroke-linecap="round"/><path d="M7 6h8M49 6h8M7 58h8M49 58h8" stroke="#e69c4a" stroke-width="7" stroke-linecap="round"/><path d="M26 19c20 0-10 12 5 15s9 10-3 12" fill="none" stroke="#fff1ce" stroke-width="2.5" stroke-linecap="round"/><circle cx="27" cy="19" r="3" fill="#fff1ce"/><circle cx="29" cy="46" r="3" fill="#fff1ce"/>',
  bag: '<defs><linearGradient id="b"><stop stop-color="#df5264"/><stop offset="1" stop-color="#b62032"/></linearGradient></defs><path fill="url(#b)" d="M10 22h44l5 35a4 4 0 0 1-4 5H9a4 4 0 0 1-4-5Z"/><path d="M21 22v-7a11 11 0 0 1 22 0v7" fill="none" stroke="#bc2e40" stroke-width="4"/><path d="M21 29c0 18 22 18 22 0" fill="none" stroke="#fff2e8" stroke-width="3.5" stroke-linecap="round"/>',
  pin: pin(red), 'pin-white': pin('#ffffff'),
  locate: outline('<circle cx="32" cy="32" r="18"/><circle cx="32" cy="32" r="6"/><path d="M32 3v11M32 50v11M3 32h11M50 32h11"/>', gray),
  shop: outline('<path d="M10 30v28h44V30M7 12h50l4 17H3ZM24 58V40h16v18M13 12l-3 17M25 12l-1 17M39 12l1 17M51 12l3 17"/>', '#8a7760')
}
const svg = (body, w = 64, h = 64) => `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${body}</svg>`
async function main() {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' })
  try {
    const page = await browser.newPage({ deviceScaleFactor: 1 })
    await page.route('**/*', route => route.abort())
    async function save(relative, artwork, width = 64, height = 64) {
      const file = path.join(root, 'miniprogram/assets', relative + '.png')
      fs.mkdirSync(path.dirname(file), { recursive: true })
      await page.setViewportSize({ width, height })
      await page.setContent(`<style>html,body{margin:0;background:transparent}svg{display:block}</style>${artwork}`)
      await page.evaluate(() => document.fonts.ready)
      await page.screenshot({ path: file, omitBackground: true })
      console.log(path.relative(root, file))
    }
    // Keep the user's source PNGs untouched; only ship a resized landscape copy.
    const source = fs.readFileSync(path.join(root, 'miniprogram/assets/lijiang-home-background.png')).toString('base64')
    // MINI-01 / DESIGN-01: keep the shipped background below 200 KB on every run.
    const landscape = await page.evaluate(data => new Promise((resolve, reject) => {
      const image = new Image()
      image.onerror = () => reject(new Error('Landscape source cannot be decoded'))
      image.onload = () => {
        const canvas = document.createElement('canvas')
        for (const width of [1125, 1000, 900]) {
          canvas.width = Math.min(width, image.naturalWidth)
          canvas.height = Math.round(image.naturalHeight * canvas.width / image.naturalWidth)
          canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height)
          for (let quality = 84; quality >= 56; quality -= 4) {
            const base64 = canvas.toDataURL('image/jpeg', quality / 100).split(',')[1]
            const bytes = atob(base64).length
            if (bytes <= 190000) {
              resolve({ base64, bytes, width: canvas.width, height: canvas.height, quality })
              return
            }
          }
        }
        reject(new Error('Landscape cannot meet the 190000-byte delivery budget'))
      }
      image.src = 'data:image/png;base64,' + data
    }), source)
    fs.mkdirSync(path.join(root, 'miniprogram/assets/home'), { recursive: true })
    fs.writeFileSync(path.join(root, 'miniprogram/assets/home/landscape.jpg'), Buffer.from(landscape.base64, 'base64'))
    console.log(`assets/home/landscape.jpg: ${landscape.bytes} bytes, ${landscape.width}x${landscape.height}, JPEG quality ${landscape.quality}`)
    // Regenerate only this derivative without touching other approved UI artwork.
    if (process.argv.includes('--landscape-only')) return
    for (const [name, body] of Object.entries(homeIcons)) await save('home/' + name, svg(body))
    for (const [name, body] of Object.entries({ home, stamp, map, user })) {
      for (const active of [false, true]) {
        const color = active ? red : gray
        const drawing = name === 'home' && active ? `<g fill="${color}" stroke="${color}" stroke-width="3" stroke-linejoin="round">${body}</g>` : outline(body, color)
        await save('tabs/' + name + (active ? '-active' : ''), svg(drawing))
      }
    }
    const fontPath = path.join(process.env.WINDIR || 'C:/Windows', 'Fonts/STXINGKA.TTF')
    const fontData = fs.readFileSync(fontPath).toString('base64')
    await save('home/brand', svg(`<style>@font-face{font-family:HomeBrush;src:url(data:font/ttf;base64,${fontData})}</style><text x="6" y="104" font-family="HomeBrush" font-size="120" fill="#111e32">东巴寻迹·丽江</text>`, 800, 130), 800, 130)
    const paper = '<defs><filter id="paper"><feTurbulence type="fractalNoise" baseFrequency=".5" numOctaves="3" seed="17"/><feColorMatrix type="saturate" values="0"/></filter><radialGradient id="wash"><stop stop-color="#fffaf1"/><stop offset="1" stop-color="#f4e5d0"/></radialGradient></defs><rect width="640" height="320" fill="url(#wash)"/><rect width="640" height="320" filter="url(#paper)" opacity=".11"/>'
    await save('home/paper', svg(paper, 640, 320), 640, 320)
    let mountain = '<defs><linearGradient id="mist" x2="0" y2="1"><stop stop-color="#807363" stop-opacity=".35"/><stop offset="1" stop-color="#807363" stop-opacity="0"/></linearGradient></defs><g stroke="#71685c" fill="url(#mist)" stroke-linejoin="round"><path d="m0 245 40-25 31-38 25 9 33-69 22 18 51-96 21 18 23-42 33 47 25-15 30 73 26-21 31 47 20-18 48 66 25-18 56 74v70H0Z" stroke-width="2"/><path d="m115 251 47-90 17 29 33-113 21 37 15-57 35 80 17-18 35 91 16-36 41 75" fill="none" stroke-width="2"/><path d="m258 242 44-65 20 28 43-102 22 40 16-22 40 73 25-23 63 69" fill="none" stroke-width="1.5"/></g>'
    for (let i = 0; i < 38; i++) {
      const x = 127 + i * 5, y = 215 - Math.abs(Math.sin(i * 1.91)) * 115
      mountain += `<path d="m${x} ${y} -${5+i%7} ${16+i%19} 3 8 -9 20" fill="none" stroke="#776b5b" opacity=".27" stroke-width="${i%3+0.5}"/>`
    }
    for (const [x,y,s] of [[371,232,1],[424,245,.8],[463,258,.65],[100,261,.55]]) {
      mountain += `<g transform="translate(${x} ${y}) scale(${s})" stroke="#635d51" stroke-width="2" fill="none"><path d="M0 30 2-17M1 0l-14-11M2-7l16-8M1 9l-20-6M2 12l22-8"/><path d="m-20-10 11-9 9 8M5-17l15-8 12 9M-27 3l10-8 10 7M9 5l14-9 12 5" stroke-width="5" opacity=".65"/></g>`
    }
    mountain += '<path d="M28 282q135-30 240 4t260-1M105 296q125-22 245-5" fill="none" stroke="#8b7f6c" opacity=".4"/>'
    await save('home/ink-mountain', svg(mountain, 540, 320), 540, 320)
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
