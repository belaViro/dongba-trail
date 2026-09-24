const test = require('node:test')
const assert = require('node:assert/strict')
const h = require('../utils/helpers')
test('null or invalid coordinates never become map points', () => {
  for (const point of [null, {}, { latitude: null, longitude: null }, { latitude: 91, longitude: 20 }, { latitude: 'bad', longitude: 100 }]) assert.equal(h.coordinates(point), false)
  assert.equal(h.coordinates({ latitude: 0, longitude: 0 }), true)
  assert.equal(h.metersBetween(null, { latitude: 0, longitude: 0 }), null)
  assert.ok(Math.abs(h.metersBetween({ latitude: 0, longitude: 0 }, { latitude: 0, longitude: 1 }) - 111195) < 1)
})
test('missing distance and confidence do not become fictional zero values', () => {
  assert.equal(h.distance(null), '')
  assert.equal(h.distance(undefined), '')
  assert.equal(h.distance(0), '0 m')
  assert.equal(h.distance(1530), '1.5 km')
  assert.equal(h.score(null), '')
  assert.equal(h.score(0.612), '61.2%')
})
test('check-ins send only evidence appropriate to their configured condition', () => {
  assert.deepEqual(h.checkinPayload({ id: 'N', condition: 'qr' }, { qr_token: 'actual-code', latitude: 30, recognition_id: 'R' }), { node_id: 'N', qr_token: 'actual-code' })
  assert.deepEqual(h.checkinPayload({ id: 'N', condition: 'geofence' }, { latitude: 26.87, longitude: 100.23 }), { node_id: 'N', latitude: 26.87, longitude: 100.23 })
  assert.deepEqual(h.checkinPayload({ id: 'N', condition: 'recognition' }, { recognition_id: 'R' }), { node_id: 'N', recognition_id: 'R' })
  assert.deepEqual(h.checkinPayload({ id: 'N', condition: 'coupon' }, { claim_id: 'C' }), { node_id: 'N', claim_id: 'C' })
  assert.throws(() => h.checkinPayload({ id: 'N', condition: 'manual' }, {}))
  assert.throws(() => h.checkinPayload({ id: 'N', condition: 'recognition' }, { qr_token: 'unrelated' }))
})
test('query parameters are escaped and undefined values are omitted', () => {
  assert.equal(h.query({ q: '茶 & 山', absent: undefined, blank: '', offset: 0 }), '?q=%E8%8C%B6%20%26%20%E5%B1%B1&offset=0')
})
test('favorite and recognition records normalize and deduplicate by canonical ID', () => {
  assert.deepEqual(h.uniqueCharacters([{ character_id: 'DB1', cn_name: 'A' }, { id: 'DB1', cn_name: 'B' }, { id: 'DB2' }]).map(value => value.id), ['DB1','DB2'])
})

