module.exports = {
  apiBase: 'https://www.liorah.top/api/v1',
  requestTimeout: 15000,
  recognitionTimeout: 45000,
  maxImageBytes: 8 * 1024 * 1024,
  privacyVersion: '2026-09-23',
  // 仅 trial/develop 跳过项目条款页；微信自身授权仍由真实按钮完成。
  experienceMode: true
}
