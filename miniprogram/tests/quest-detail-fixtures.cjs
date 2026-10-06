// QUEST-01 / QUEST-02 / DESIGN-01: layout fixtures, not approved cultural content.
function questDetailFixture(overrides = {}) {
  return {
    loading: false, error: '', busy: '', reward: null, closed: false, heroFailed: false,
    item: { id: 'fixture-route', area: '丽江', name: '寻迹详情布局示例', description: '仅用于离线排版检查，不是真实路线。', reward_coupon_id: 'fixture-coupon' },
    progress: { status: 'enrolled', completed_node_ids: [], reward_pending: false },
    completed: 0, percent: 0,
    nodes: [
      { id: 'both', name: '商户与点位均有关联的示例节点', condition: 'qr', merchant_id: 'fixture-merchant', poi_id: 'fixture-poi', is_next: true },
      { id: 'poi', name: '独立文化点位示例', condition: 'geofence', poi_id: 'fixture-culture' },
      { id: 'merchant', name: '仅关联商户的示例节点', condition: 'recognition', merchant_id: 'fixture-shop' },
      { id: 'manual', name: '人工确认示例', condition: 'manual' },
      { id: 'coupon', name: '核销验证示例', condition: 'coupon' }
    ],
    ...overrides
  }
}
function configuredQuestFixtures() {
  // Reuse repository demo wording verbatim; this does not query or populate a DB.
  const source = require('../../data/operational_demo.json')
  return source.quests.map(([id, name, description, area, reward_coupon_id]) => questDetailFixture({
    item: { id, name, description, area, reward_coupon_id },
    nodes: source.quest_nodes.filter(row => row[1] === id).map(([nodeId, quest_id, nodeName, sequence, condition, character_id, merchant_id, poi_id]) => ({ id: nodeId, quest_id, name: nodeName, sequence, condition, character_id, merchant_id, poi_id }))
      .sort((a, b) => a.sequence - b.sequence).map((node, index) => ({ ...node, is_next: index === 0 }))
  }))
}
module.exports = { questDetailFixture, configuredQuestFixtures }
