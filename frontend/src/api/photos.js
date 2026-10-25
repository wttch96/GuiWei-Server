import request from './request'

export const uploadPhoto = (file, itemId) => {
  const form = new FormData()
  form.append('file', file)
  if (itemId) form.append('item_id', itemId)
  return request.post('/photos', form)
}

export const listPhotos = (params = {}) => request.get('/photos', { params })

export const getPhoto = (photoId) => request.get(`/photos/${photoId}`)

export const batchDeletePhotos = (ids) =>
  request.post('/photos/batch-delete', { ids })

export const attachPhoto = (photoId, itemId) =>
  request.post(`/photos/${photoId}/attach`, { item_id: itemId })

export const setPrimaryPhoto = (photoId) => request.post(`/photos/${photoId}/primary`)

export const deletePhoto = (photoId) => request.delete(`/photos/${photoId}`)

export const analyzePhoto = (photoId, data = {}) =>
  request.post(`/photos/${photoId}/analyze`, data ?? {}, { timeout: 180000 })

export const findSimilarItems = (photoId, data = {}) =>
  request.post(`/photos/${photoId}/similar`, data ?? {}, { timeout: 30000 })

/** YOLO-World 多物品检测与裁切，首次运行会下载模型，耗时可能较长。 */
export const detectPhoto = (photoId) =>
  request.post(`/photos/${photoId}/detect`, {}, { timeout: 180000 })
