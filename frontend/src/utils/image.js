/** 浏览器端图片缩放工具：拍照上传前先把短边压到 480p，减少流量与后端处理耗时。 */

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('图片读取失败'))
    img.src = src
  })
}

function canvasToBlob(canvas, type, quality) {
  return new Promise((resolve) => {
    if (canvas.toBlob) {
      canvas.toBlob(resolve, type, quality)
      return
    }
    // 极旧浏览器的兜底
    const dataUrl = canvas.toDataURL(type, quality)
    const base64 = dataUrl.split(',')[1] || ''
    const binary = atob(base64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
    resolve(new Blob([bytes], { type }))
  })
}

/**
 * 把照片的短边缩放到 480p（竖拍为 480×~853，横拍为 ~853×480）。
 * 原图短边不超过 480 时保持原样；始终输出 JPEG，避免 HEIC 等格式后端无法解析。
 * @param {File} file
 * @param {number} shortEdge 目标短边像素，默认 480
 * @returns {Promise<File>}
 */
export async function downscalePhoto(file, shortEdge = 480) {
  if (!file || !file.type?.startsWith('image/')) return file
  const url = URL.createObjectURL(file)
  try {
    const img = await loadImage(url)
    const minEdge = Math.min(img.naturalWidth, img.naturalHeight)
    if (!minEdge) return file

    const width = img.naturalWidth
    const height = img.naturalHeight
    const scale = minEdge > shortEdge ? shortEdge / minEdge : 1
    const targetWidth = Math.round(width * scale)
    const targetHeight = Math.round(height * scale)

    // 原图本身就在 480p 以内时，也重新编码一次，顺手统一为 JPEG
    const canvas = document.createElement('canvas')
    canvas.width = targetWidth
    canvas.height = targetHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return file
    ctx.drawImage(img, 0, 0, targetWidth, targetHeight)

    const blob = await canvasToBlob(canvas, 'image/jpeg', 0.85)
    if (!blob) return file
    const name = (file.name || 'photo').replace(/\.[^.]+$/, '') || 'photo'
    return new File([blob], `${name}.jpg`, { type: 'image/jpeg', lastModified: Date.now() })
  } catch {
    // 缩放失败就退回原图，不阻断上传
    return file
  } finally {
    URL.revokeObjectURL(url)
  }
}
