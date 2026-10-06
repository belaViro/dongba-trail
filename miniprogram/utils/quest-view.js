// QUEST-01 / QUEST-02 / DESIGN-01: presentation only; the server decides completion.
const conditions = {
  recognition: { label: '识字', icon: 'camera', action: '拍照识字，留下一枚印记' },
  qr: { label: '扫码', icon: 'paper', action: '找到任务二维码，扫码打卡' },
  geofence: { label: '到访', icon: 'pin', action: '走到任务地点，留下到访印记' },
  coupon: { label: '核销', icon: 'bag', action: '完成指定核销，收集这枚印记' },
  manual: { label: '确认', icon: 'scroll', action: '由工作人员确认任务完成' }
}

function questView(item, progress, now = Date.now(), media = {}) {
  const ids = new Set(progress && progress.completed_node_ids || [])
  const source = (item.nodes || []).slice().sort((a, b) => a.sequence - b.sequence || String(a.id).localeCompare(String(b.id)))
  const nextId = (source.find(node => !ids.has(node.id)) || {}).id
  const dense = source.length >= 9 && source.length <= 12
  const nodes = source.map((node, index) => {
    const condition = conditions[node.condition] || { label: '任务', icon: 'scroll', action: '查看任务详情，了解完成方式' }
    const character = (media.characters || {})[node.character_id] || {}
    const merchant = (media.merchants || {})[node.merchant_id] || {}
    const angle = -Math.PI / 2 + index * Math.PI * 2 / source.length
    return Object.assign({}, node, {
      number: String(index + 1).padStart(2, '0'),
      condition_name: condition.label,
      action_hint: condition.action,
      icon: '/assets/home/' + condition.icon + '.png',
      glyph_url: character.image_url || '',
      glyph_name: character.cn_name || '',
      place_image: merchant.image_url || '',
      place_name: merchant.name || '',
      completed: ids.has(node.id),
      is_next: node.id === nextId,
      orbit_style: 'left:' + (50 + (dense ? 42.3 : 40) * Math.cos(angle)).toFixed(3) + '%;top:' + (50 + 40 * Math.sin(angle)).toFixed(3) + '%;'
    })
  })
  const completed = nodes.filter(node => node.completed).length
  const closed = !!(item.unavailable || (item.start_at && now < new Date(item.start_at).getTime()) || (item.end_at && now >= new Date(item.end_at).getTime()))
  return {
    item, progress, nodes, completed, total: nodes.length, closed,
    next: nodes.find(node => node.is_next) || null,
    complete: !!(progress && progress.status === 'completed'),
    compact: nodes.length > 12, dense, sparse: nodes.length <= 4,
    action_label: closed ? '查看路线记录' : progress ? (progress.status === 'completed' ? '回顾我的寻迹' : '继续寻迹') : '开启这段寻迹'
  }
}

module.exports = { questView }
