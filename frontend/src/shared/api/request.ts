import axios from 'axios'
import { ElMessage } from 'element-plus'

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
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') {
      msg = detail
    } else if (Array.isArray(detail) && detail.length > 0) {
      // 422 校验错误数组，取第一条拼接位置与原因
      const first = detail[0]
      const loc = (first.loc ?? []).filter((p: unknown) => p !== 'body').join('.')
      msg = `参数错误${loc ? `（${loc}）` : ''}：${first.msg}`
    }
    ElMessage.error(msg)
    return Promise.reject(error)
  },
)

export default request