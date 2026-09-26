import { describe, expect, it } from 'vitest'
import { gcj02ToWgs84, validPoiCoordinates } from '../src/map-coordinates'

describe('GEO-01 backend POI map coordinates', () => {
  it('converts Chinese GCJ-02 locations to the WGS-84 tile system', () => {
    const [lat, lng] = gcj02ToWgs84(26.875, 100.235)
    expect(lat).toBeGreaterThan(26.87)
    expect(lat).toBeLessThan(26.88)
    expect(lng).toBeGreaterThan(100.22)
    expect(lng).toBeLessThan(100.24)
    expect(gcj02ToWgs84(40, -73)).toEqual([40, -73])
  })
  it('rejects missing and invalid point coordinates instead of drawing arbitrary pins', () => {
    expect(validPoiCoordinates({ latitude: null, longitude: null })).toBe(false)
    expect(validPoiCoordinates({ latitude: 0, longitude: 0 })).toBe(false)
    expect(validPoiCoordinates({ latitude: 99, longitude: 100 })).toBe(false)
    expect(validPoiCoordinates({ latitude: 26.875, longitude: 100.235 })).toBe(true)
  })
})
