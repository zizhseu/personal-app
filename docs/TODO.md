# 后续事项

## 小红书采集方式选择（2026-10-19 记录，2026-10-25 接入）

- 用户希望同时支持当前 `xpzouying/xiaohongshu-mcp` 和 [jackwener/xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli)，在设置中自由选择使用哪一种方式。
- 保留现有 OCR、文字校对、AI 整理和问答入库流程；切换只影响内容采集。
- 已验证 CLI 在 Windows 上的扫码、真实搜索、正文、图片获取及样本 OCR；两种方式分别管理登录与连接状态，结果见 [验证记录](validation-content-sources-2026-10-25.md)。
- 2026-10-25 已接入平台与实现注册表、设置选择、分别登录、结果归属和统一材料校验，说明见 [内容来源](content-sources.md)。
- 知乎、B 站后续先确定采集及鉴权方案，再按同一契约新增适配器；当前未实现这两个来源。
