const scenes = [
  { value: 'other', label: '其他场景' },
  { value: 'paper', label: '纸本文献' },
  { value: 'shop_sign', label: '商户招牌' },
  { value: 'wall', label: '墙面' },
  { value: 'wood', label: '木牌木刻' },
  { value: 'product', label: '文创商品' },
  { value: 'screen', label: '屏幕图片' }
]
const reviewStates = { pending: '待人工复核', reviewed: '已复核', approved: '已通过', rejected: '未通过' }
function sceneLabel(value) { const scene = scenes.find(item => item.value === value); return scene ? scene.label : '其他场景' }
module.exports = { scenes, sceneLabel, reviewStates }
