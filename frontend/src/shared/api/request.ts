import axios from 'axios'
import { ElMessage } from 'element-plus'

declare module 'axios' {
  interface AxiosRequestConfig {
    /** 自动保存等后台请求在页面内呈现错误，避免重复弹窗。 */
    silentError?: boolean
  }
}

/** 后端模型调用最多等待 120 秒，另预留 10 秒用于接口处理和传输。 */
export const AI_REQUEST_TIMEOUT_MS = 130_000

/** 统一 axios 实例：走 Vite 代理到后端 /api */
const request = axios.create({
  baseURL: '/api',
  timeout: 10_000,
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // 提取 FastAPI 错误信息并弹中文提示
    let msg = '请求失败，请稍后重试'
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      msg = '请求超时，请稍后重试'
    }
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') {
      msg = detail
    } else if (Array.isArray(detail) && detail.length > 0) {
      // 422 校验错误数组，取第一条拼接位置与原因
      const first = detail[0]
      const loc = (first.loc ?? []).filter((p: unknown) => p !== 'body').join('.')
      msg = `参数错误${loc ? `（${loc}）` : ''}：${first.msg}`
    }
    if (!error.config?.silentError) ElMessage.error(msg)
    return Promise.reject(error)
  },
)

export default request
