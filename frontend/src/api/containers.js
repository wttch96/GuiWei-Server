import request from './request'

export const listContainers = (roomId) =>
  request.get('/containers', { params: { room_id: roomId } })
export const getContainerTree = (roomId) =>
  request.get('/containers/tree', { params: { room_id: roomId } })
export const createContainer = (data) => request.post('/containers', data)
export const updateContainer = (id, data) => request.put(`/containers/${id}`, data)
export const moveContainer = (id, data) => request.post(`/containers/${id}/move`, data)
export const deleteContainer = (id) => request.delete(`/containers/${id}`)
