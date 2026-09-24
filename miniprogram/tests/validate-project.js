const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const root = path.resolve(__dirname, '..')
const app = JSON.parse(fs.readFileSync(path.join(root, 'app.json'), 'utf8'))
const errors = []
const files = []
function visit(directory) {
  for (const name of fs.readdirSync(directory)) {
    const file = path.join(directory, name)
    if (fs.statSync(file).isDirectory()) visit(file)
    else files.push(file)
  }
}
visit(root)
for (const file of files) {
  if (file.endsWith('.json')) {
    try { JSON.parse(fs.readFileSync(file, 'utf8')) } catch (error) { errors.push(path.relative(root,file) + ': ' + error.message) }
  }
  if (file.endsWith('.js')) {
    try { new vm.Script(fs.readFileSync(file, 'utf8'), { filename: file }) } catch (error) { errors.push(error.message) }
  }
}
for (const page of app.pages) {
  for (const extension of ['js','wxml','json']) if (!fs.existsSync(path.join(root, page + '.' + extension))) errors.push(page + '.' + extension + ' missing')
  const source = fs.readFileSync(path.join(root, page + '.js'), 'utf8')
  const markup = fs.readFileSync(path.join(root, page + '.wxml'), 'utf8')
  for (const match of markup.matchAll(/(?:bind|catch)(?::)?[a-z]+="([a-zA-Z][a-zA-Z0-9_]*)"/g)) {
    if (!new RegExp('\\b' + match[1] + '\\s*\\(').test(source)) errors.push(page + ': missing event handler ' + match[1])
  }
}
for (const item of app.tabBar.list) assert.ok(app.pages.includes(item.pagePath), 'Tab route registered')
for (const category of ['culture','merchant','quest']) assert.ok(fs.existsSync(path.join(root, 'assets/marker-' + category + '.png')), 'Native map marker asset exists')
for (const file of files.filter(file => /\.js$/.test(file) && !file.includes(path.sep + 'tests' + path.sep))) {
  const source = fs.readFileSync(file, 'utf8')
  for (const match of source.matchAll(/['"](\/pages\/[a-z-]+\/index)(?:\?[^'"]*)?['"]/g)) {
    if (!app.pages.includes(match[1].slice(1))) errors.push(path.relative(root,file) + ': unknown route ' + match[1])
  }
}
assert.equal(errors.length, 0, errors.join('\n'))
console.log('Validated ' + app.pages.length + ' native pages, JSON/JS syntax, tab routes and WXML event handlers.')
const fingerprint = crypto.createHash('sha256')
for (const file of files.filter(value => /\.(js|json|wxml|wxss|png|py)$/.test(value)).sort()) {
  fingerprint.update(path.relative(root, file).replace(/\\/g, '/') + '\n')
  fingerprint.update(fs.readFileSync(file))
  fingerprint.update('\n')
}
console.log('Mini-program code SHA-256: ' + fingerprint.digest('hex'))
