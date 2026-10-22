import request from './request'

export const globalSearch = (q) => request.get('/search', { params: { q } })
