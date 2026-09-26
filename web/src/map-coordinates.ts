// GEO-01: Backend coordinates use GCJ-02; AMap uses GCJ-02 directly (old WGS conversion retained for other consumers).
const pi = Math.PI
const a = 6378245
const ee = 0.006693421622965943

function offset(latitude: number, longitude: number): [number, number] {
  if (longitude < 73.66 || longitude > 135.05 || latitude < 3.86 || latitude > 53.55) return [0, 0]
  const x = longitude - 105
  const y = latitude - 35
  let lat = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x))
  lat += ((20 * Math.sin(6 * x * pi) + 20 * Math.sin(2 * x * pi)) * 2) / 3
  lat += ((20 * Math.sin(y * pi) + 40 * Math.sin((y / 3) * pi)) * 2) / 3
  lat += ((160 * Math.sin((y / 12) * pi) + 320 * Math.sin((y * pi) / 30)) * 2) / 3
  let lng = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x))
  lng += ((20 * Math.sin(6 * x * pi) + 20 * Math.sin(2 * x * pi)) * 2) / 3
  lng += ((20 * Math.sin(x * pi) + 40 * Math.sin((x / 3) * pi)) * 2) / 3
  lng += ((150 * Math.sin((x / 12) * pi) + 300 * Math.sin((x / 30) * pi)) * 2) / 3
  const rad = (latitude / 180) * pi
  const magic = 1 - ee * Math.sin(rad) ** 2
  const sqrt = Math.sqrt(magic)
  return [
    (lat * 180) / (((a * (1 - ee)) / (magic * sqrt)) * pi),
    (lng * 180) / ((a / sqrt) * Math.cos(rad) * pi),
  ]
}

export function gcj02ToWgs84(latitude: number, longitude: number): [number, number] {
  let lat = latitude
  let lng = longitude
  for (let i = 0; i < 3; i++) {
    const [dLat, dLng] = offset(lat, lng)
    lat = latitude - dLat
    lng = longitude - dLng
  }
  return [lat, lng]
}

export function validPoiCoordinates(row: { latitude?: unknown; longitude?: unknown }): boolean {
  const lat = Number(row.latitude)
  const lng = Number(row.longitude)
  return (
    row.latitude != null &&
    row.longitude != null &&
    Number.isFinite(lat) &&
    Number.isFinite(lng) &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180 &&
    lat !== 0 &&
    lng !== 0
  )
}
