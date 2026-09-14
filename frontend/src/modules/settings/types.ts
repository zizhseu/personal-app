/** 全局应用偏好（localStorage 持久化，不进后端） */
export interface AppSettings {
  /** 导入题目时把文件名（去扩展名）作为标签加到该批题目 */
  importFilenameAsTag: boolean
}