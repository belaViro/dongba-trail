// MINI-01 / AI-01, D-065: route recognition through the framing capture page.
// Photos are taken at original resolution, framed with the four-corner guide
// and cropped locally before upload, so surrounding text/background is excluded.
// A gallery entry reuses the same framing step.
function start(options) {
  const opts = options || {}
  const app = getApp()
  app.globalData.activeQuest = opts.quest && opts.node ? { quest_id: opts.quest, node_id: opts.node } : null
  const query = []
  if (opts.source === 'album') query.push('source=album')
  if (opts.quest) query.push('quest=' + encodeURIComponent(opts.quest))
  if (opts.node) query.push('node=' + encodeURIComponent(opts.node))
  wx.navigateTo({ url: '/pages/capture/index' + (query.length ? '?' + query.join('&') : '') })
}
function camera(options) { start(options) }
function album(options) { start(Object.assign({}, options || {}, { source: 'album' })) }
function chooseCamera(options) { return camera(options) }
function chooseAlbum(options) { return album(options) }
module.exports = { start, camera, album, chooseCamera, chooseAlbum }
