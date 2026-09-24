const fs = require('fs')
const path = require('path')
const assert = require('assert').strict
const { spawnSync } = require('child_process')

const installation = process.argv[2]
if (!installation) throw new Error('Pass the installed WeChat developer-tools directory as the first argument')
const compilerRoot = path.join(installation, 'code/package.nw/node_modules/wcc-exec')
const root = path.resolve(__dirname, '..')
const files = []
function visit(directory) {
  for (const name of fs.readdirSync(directory)) {
    const file = path.join(directory, name)
    if (fs.statSync(file).isDirectory()) visit(file)
    else files.push(path.relative(root, file).replace(/\\/g, '/'))
  }
}
visit(root)

async function main() {
  const templates = files.filter(file => file.endsWith('.wxml'))
  const styles = files.filter(file => file.endsWith('.wxss'))
  const compile = (name, argumentsList) => {
    const result = spawnSync(path.join(compilerRoot, name + '.exe'), argumentsList, { cwd: root, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024, windowsHide: true })
    if (result.error) throw result.error
    if (result.status !== 0) throw new Error(name + ' failed: ' + result.stderr + result.stdout)
    if (result.stderr.trim()) console.log(name + ' diagnostics: ' + result.stderr.trim())
    return result.stdout
  }
  const markup = compile('wcc', templates)
  assert.ok(markup.length > 0, 'WXML compiler returned generated code')
  const css = compile('wcsc', ['-pc', String(styles.length), ...styles])
  assert.ok(css.length > 0, 'WXSS compiler returned generated styles')
  console.log('WeChat native compiler accepted ' + templates.length + ' WXML files and ' + styles.length + ' WXSS files.')
  console.log('This is native template/style compilation, not a signed upload or real-device verification.')
}
main().catch(error => { console.error(error.message); process.exitCode = 1 })
