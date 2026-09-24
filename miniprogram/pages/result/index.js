const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
Page({
  data: { result: null, image: '', candidates: [], selected: '', busy: false, error: '', comment: '', submitted: false },
  async onLoad() {
    const app = getApp(); const result = app.globalData.recognition
    if (!result) { this.setData({ error: '识别结果已失效，请重新拍摄' }); return }
    if (result.status === 'FAILED') { this.setData({ error: api.errorFrom(503, { code: result.error_code }).message }); return }
    this.setData({ result, image: app.globalData.recognitionImage, candidates: (result.candidates || []).slice(0,5).map(item => Object.assign(helpers.normalizeCharacter(item), { image_url: api.mediaUrl(item.image_url), score_text: helpers.score(item.provider_score) })) })
    const candidates = await Promise.all(this.data.candidates.map(async candidate => {
      if (candidate.image_url) return candidate
      try {
        const detail = await api.request('/characters/' + encodeURIComponent(candidate.id))
        return Object.assign({}, candidate, { image_url: api.mediaUrl(detail.image_url) })
      } catch (_) { return candidate }
    }))
    this.setData({ candidates })
  },
  choose(event) { this.setData({ selected: event.currentTarget.dataset.id }) },
  comment(event) { this.setData({ comment: event.detail.value }) },
  retake() {
    const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
    const previous = pages[pages.length - 2]
    if (previous && previous.route === 'pages/camera/index') {
      previous.retake(); wx.navigateBack()
    } else wx.redirectTo({ url: '/pages/camera/index' })
  },
  async submit(event) {
    const characterId = event.currentTarget.dataset.unknown ? null : this.data.selected
    if (this.data.busy || !this.data.result || (!event.currentTarget.dataset.unknown && !characterId)) return
    this.setData({ busy: true, error: '' })
    try {
      await api.request('/recognize/' + encodeURIComponent(this.data.result.request_id) + '/confirm', { method: 'POST', auth: true, data: { character_id: characterId, comment: this.data.comment || (characterId ? '' : '候选均不匹配，请人工复核') } })
      const app = getApp()
      if (characterId) {
        if (app.globalData.activeQuest) {
          const quest = app.globalData.activeQuest
          try {
            await api.request('/quests/' + encodeURIComponent(quest.quest_id) + '/checkin', { method: 'POST', auth: true, data: { node_id: quest.node_id, recognition_id: this.data.result.request_id } })
            app.globalData.activeQuest = null
          } catch (error) { api.showError(error) }
        }
        wx.redirectTo({ url: '/pages/character/index?id=' + encodeURIComponent(characterId) + '&recognition_id=' + encodeURIComponent(this.data.result.request_id) })
      } else this.setData({ submitted: true })
    } catch (error) { this.setData({ error: error.message, requestId: error.requestId || '' }) }
    finally { this.setData({ busy: false }) }
  }
})
