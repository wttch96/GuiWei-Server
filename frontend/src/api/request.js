import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 60000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('guiwei_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => {
    const payload = response.data
    if (payload && typeof payload === 'object' && 'code' in payload) {
      if (payload.code === 0) return payload.data
      ElMessage.error(payload.message || '请求失败')
      return Promise.reject(new Error(payload.message || '请求失败'))
    }
    return payload
  },
  (error) => {
    const status = error.response?.status
    const message =
      error.response?.data?.message || error.message || '网络异常，请稍后重试'
    const isLoginRequest = error.config?.url?.includes('/auth/login')

    if (status === 401 && !isLoginRequest) {
      localStorage.removeItem('guiwei_token')
      localStorage.removeItem('guiwei_admin')
      if (!window.location.pathname.startsWith('/login')) {
        window.location.replace('/login')
      }
    }
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default request
