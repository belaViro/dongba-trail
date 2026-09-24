function items(value) { return Array.isArray(value) ? value : (value && Array.isArray(value.items) ? value.items : []) }
function identifier(value) { return value && (value.character_id || value.id) }
function query(values) {
  const pairs = Object.keys(values || {}).filter(key => values[key] !== null && values[key] !== undefined && values[key] !== '')
  return pairs.length ? '?' + pairs.map(key => encodeURIComponent(key) + '=' + encodeURIComponent(values[key])).join('&') : ''
}
function date(value) {
  if (!value) return ''
  const time = new Date(value)
  return Number.isNaN(time.getTime()) ? '' : [time.getFullYear(), String(time.getMonth()+1).padStart(2,'0'), String(time.getDate()).padStart(2,'0')].join('.')
}
function distance(value) {
  const number = Number(value)
  if (value === null || value === undefined || !Number.isFinite(number) || number < 0) return ''
  return number < 1000 ? Math.round(number) + ' m' : (number / 1000).toFixed(1) + ' km'
}
function coordinates(value) {
  return !!value && value.latitude !== null && value.longitude !== null && value.latitude !== undefined && value.longitude !== undefined &&
    Number.isFinite(Number(value.latitude)) && Math.abs(Number(value.latitude)) <= 90 &&
    Number.isFinite(Number(value.longitude)) && Math.abs(Number(value.longitude)) <= 180
}
function metersBetween(origin, target) {
  if (!coordinates(origin) || !coordinates(target)) return null
  const radians = Math.PI / 180
  const deltaLatitude = (Number(target.latitude) - Number(origin.latitude)) * radians
  const deltaLongitude = (Number(target.longitude) - Number(origin.longitude)) * radians
  const a = Math.sin(deltaLatitude / 2) ** 2 + Math.cos(Number(origin.latitude) * radians) * Math.cos(Number(target.latitude) * radians) * Math.sin(deltaLongitude / 2) ** 2
  return 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)))
}
function normalizeCharacter(value) { return Object.assign({}, value, { id: identifier(value) }) }
function score(value) { return typeof value === 'number' && Number.isFinite(value) ? (value * 100).toFixed(1) + '%' : '' }
function uniqueCharacters(values) {
  const map = new Map()
  values.forEach(item => { if (identifier(item)) map.set(identifier(item), normalizeCharacter(item)) })
  return Array.from(map.values())
}
function checkinPayload(node, values) {
  const payload = { node_id: node.id }
  if (node.condition === 'recognition' && values.recognition_id) payload.recognition_id = values.recognition_id
  else if (node.condition === 'qr' && values.qr_token) payload.qr_token = values.qr_token
  else if (node.condition === 'geofence' && coordinates(values)) { payload.latitude = Number(values.latitude); payload.longitude = Number(values.longitude) }
  else if (node.condition === 'coupon' && values.claim_id) payload.claim_id = values.claim_id
  else throw new Error('该节点尚未具备打卡条件')
  return payload
}
module.exports = { items, identifier, query, date, distance, coordinates, metersBetween, normalizeCharacter, uniqueCharacters, score, checkinPayload }
