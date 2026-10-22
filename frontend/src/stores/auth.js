import { defineStore } from 'pinia'
import * as authApi from '../api/auth'

function readAdmin() {
  try {
    return JSON.parse(localStorage.getItem('guiwei_admin') || 'null')
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('guiwei_token') || '',
    admin: readAdmin(),
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
    adminName: (state) => state.admin?.username || '管理员',
  },
  actions: {
    async login(form) {
      const data = await authApi.login(form)
      this.token = data.token
      this.admin = data.admin
      localStorage.setItem('guiwei_token', data.token)
      localStorage.setItem('guiwei_admin', JSON.stringify(data.admin || {}))
      return data
    },
    async fetchMe() {
      const admin = await authApi.getMe()
      this.admin = admin
      localStorage.setItem('guiwei_admin', JSON.stringify(admin || {}))
      return admin
    },
    logout() {
      this.token = ''
      this.admin = null
      localStorage.removeItem('guiwei_token')
      localStorage.removeItem('guiwei_admin')
    },
  },
})
