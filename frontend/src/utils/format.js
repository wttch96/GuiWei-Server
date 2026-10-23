import dayjs from 'dayjs'

export function formatDate(value, template = 'YYYY-MM-DD HH:mm') {
  if (!value) return '—'
  return dayjs(value).format(template)
}

export function fromNow(value) {
  if (!value) return '—'
  const target = dayjs(value)
  const diff = dayjs().diff(target, 'minute')
  if (diff < 1) return '刚刚'
  if (diff < 60) return `${diff} 分钟前`
  if (diff < 60 * 24) return `${Math.floor(diff / 60)} 小时前`
  if (diff < 60 * 24 * 7) return `${Math.floor(diff / 1440)} 天前`
  return target.format('YYYY-MM-DD')
}

export const COLOR_FAMILIES = [
  '黑色',
  '白色',
  '灰色',
  '米色',
  '棕色',
  '红色',
  '橙色',
  '黄色',
  '绿色',
  '青色',
  '蓝色',
  '紫色',
  '粉色',
  '彩色',
  '其他',
]

export const STATUS_OPTIONS = [
  { value: 'in_stock', label: '在库', type: 'success' },
  { value: 'lent', label: '借出', type: 'warning' },
  { value: 'used_up', label: '用完', type: 'info' },
  { value: 'discarded', label: '已丢弃', type: 'danger' },
]

export function statusInfo(status) {
  return STATUS_OPTIONS.find((item) => item.value === status) || {
    value: status,
    label: status || '未知',
    type: 'info',
  }
}

export function photoUrl(photoOrId) {
  const id = typeof photoOrId === 'object' ? photoOrId?.id : photoOrId
  if (!id) return ''
  const token = localStorage.getItem('guiwei_token') || ''
  return `/api/photos/${id}/file?token=${encodeURIComponent(token)}`
}

export function photoDownloadUrl(photoOrId) {
  const id = typeof photoOrId === 'object' ? photoOrId?.id : photoOrId
  if (!id) return ''
  const token = localStorage.getItem('guiwei_token') || ''
  return `/api/photos/${id}/file?download=1&token=${encodeURIComponent(token)}`
}

export function formatBytes(value) {
  const size = Number(value) || 0
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`
}

export function prettyJson(value) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value ?? '')
  }
}
