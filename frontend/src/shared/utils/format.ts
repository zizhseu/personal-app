import dayjs from 'dayjs'

/** 日期：2026-09-08 */
export function formatDate(value?: string | null): string {
  return value ? dayjs(value).format('YYYY-MM-DD') : '—'
}

/** 日期时间：2026-09-08 14:00 */
export function formatDateTime(value?: string | null): string {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '—'
}

/** 今天日期字符串（YYYY-MM-DD） */
export function today(): string {
  return dayjs().format('YYYY-MM-DD')
}