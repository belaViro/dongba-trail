// DESIGN-01: offline UI fixtures only; never loaded by application pages.
const { makeQuestFixture } = require('./quest-fixtures')
function questFixture(count = 3, completed = 1, extra = {}, options = {}) {
  return makeQuestFixture(count, { completed, complete: completed === count && count > 0, item: extra, ...options })
}
module.exports = { questFixture }
