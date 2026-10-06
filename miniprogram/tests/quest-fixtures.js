// Offline layout fixtures only. These are not published routes or cultural content.
const { questView } = require('../utils/quest-view')
function makeQuestFixture(count = 3, options = {}) {
  const conditions = ['qr', 'geofence', 'recognition', 'coupon', 'manual']
  const nodes = Array.from({ length: count }, (_, i) => ({ id: 'fixture-node-' + i, name: ['纸坊扫码留印', '古城到访打卡', '寻找东巴文字'][i % 3], condition: conditions[i % 5], sequence: i + 1, character_id: i % 3 === 2 ? 'fixture-character' : null, merchant_id: 'fixture-merchant-' + (i % 3) }))
  const item = { id: 'fixture-quest', name: '古城文化寻迹（布局示例）', area: '丽江古城', description: '本段内容仅用于离线排版测试，不是真实活动或文化解释。', nodes, reward_coupon_id: 'fixture-reward', ...options.item }
  const progress = options.guest ? null : { status: options.complete ? 'completed' : 'enrolled', completed_node_ids: nodes.slice(0, options.complete ? count : options.completed ?? Math.min(1, count)).map(node => node.id), reward_pending: !!options.complete }
  const merchants = Object.fromEntries(nodes.map(node => [node.merchant_id, { name: '商户图片布局示例', image_url: '/assets/home/landscape.jpg' }]))
  const feature = questView(item, progress, Date.now(), options.noMedia ? {} : { merchants })
  return { items: [item], all: [item], filter: 'all', selectedId: item.id, feature, featureLoading: false, featureError: '', loading: false, error: '', rewardTitle: '纸绘体验券（布局示例）', rewardUnavailable: false }
}
module.exports = { makeQuestFixture }
