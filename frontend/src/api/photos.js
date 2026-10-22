import request from './request'

export const uploadPhoto = (file, itemId) => {
  const form = new FormData()
  form.append('file', file)
  if (itemId) form.append('item_id', itemId)
  return request.post('/photos', form)
}

export const listPhotos = (itemId) =>
  request.get('/photos', { params: { item_id: itemId } })

export const attachPhoto = (photoId, itemId) =>
  request.post(`/photos/${photoId}/attach`, { item_id: itemId })

export const setPrimaryPhoto = (photoId) => request.post(`/photos/${photoId}/primary`)

export const deletePhoto = (photoId) => request.delete(`/photos/${photoId}`)

export const analyzePhoto = (photoId, data) =>
  request.post(`/photos/${photoId}/analyze`, data, { timeout: 180000 })
