import request from './request'

export const listItems = (params) => request.get('/items', { params })
export const getItem = (id) => request.get(`/items/${id}`)
export const createItem = (data) => request.post('/items', data)
export const updateItem = (id, data) => request.put(`/items/${id}`, data)
export const moveItem = (id, data) => request.post(`/items/${id}/move`, data)
export const deleteItem = (id) => request.delete(`/items/${id}`)
