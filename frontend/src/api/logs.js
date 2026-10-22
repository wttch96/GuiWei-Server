import request from './request'

export const listLogs = (params) => request.get('/logs', { params })
