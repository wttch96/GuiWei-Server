import request from './request'

export const listRooms = () => request.get('/rooms')
export const getRoom = (id) => request.get(`/rooms/${id}`)
export const createRoom = (data) => request.post('/rooms', data)
export const updateRoom = (id, data) => request.put(`/rooms/${id}`, data)
export const deleteRoom = (id) => request.delete(`/rooms/${id}`)
export const getRoomTree = (id) => request.get(`/rooms/${id}/tree`)
