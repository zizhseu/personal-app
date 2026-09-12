import type { AppModule } from '@/shared/types/module'
import { jobsModule } from './jobs'
import { qaModule } from './qa'

/**
 * 模块注册表：新增功能模块只需在此 import 并加入数组，
 * 路由与菜单随之自动生成，无需改动其他代码。
 */
export const modules: AppModule[] = [jobsModule, qaModule]