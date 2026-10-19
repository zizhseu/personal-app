# 大模型设置

进入「设置 → 大模型」。AI 面试、根据回答追问、面试复盘和选择题解析共用这里保存的连接，保存后无需重启后端。正在执行的请求继续使用开始时读取的配置，之后的请求使用新配置。

## 使用 API Key

1. 选择 DeepSeek、OpenAI API 或自定义兼容服务。预设只填入地址和接口格式，OpenAI 模型需从列表选择或手动填写。
2. 填写服务商给出的 Base URL，例如 `https://api.openai.com/v1`。自定义地址也支持本机服务。完整的 `/chat/completions` 或 `/responses` 地址会规范化为基础地址，避免重复拼接。
3. 输入该服务的 API Key。模型名必须与服务商提供的标识一致；可以获取列表，也可以直接输入并选择新建选项。
4. 选择接口格式：常见兼容服务使用 Chat Completions；支持 Responses 的服务可选择 Responses。无需认证的本地模型可关闭「使用 API Key」。
5. 测试连接，确认可用后保存。测试使用当前表单，不修改已保存的连接，也不发送简历；会发出一次真实模型请求，可能产生少量费用。

密钥输入框不会回填原始密钥。同一个地址与供应商下，留空保留已有密钥；填写新值替换；勾选「保存时清除密钥」后保存即可清除。更换地址或供应商时，空白输入不会继承旧服务的密钥。

界面配置优先于 `backend/.env`。在界面清除密钥后，不会重新启用 `.env` 中的旧密钥。尚未在界面保存的连接继续使用 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`、`LLM_API_STYLE` 默认值；修改这些启动默认值需要重启。

「已配置」只表示配置和本地授权记录齐备；模型目录也不能证明当前账号有推理权限。是否可完成一次推理，应以连接测试结果为准。

## 使用 ChatGPT 账号

1. 切换至「ChatGPT 账号」，点击 **Continue with ChatGPT**，在打开的 OpenAI 页面登录并授权。弹窗被拦截时可点击「打开授权页面」。不要在应用中输入 ChatGPT 密码或粘贴登录令牌。
2. 返回设置等待连接完成。若只允许了身份登录、未允许套餐使用，需重新授权套餐权限。首次授权套餐时会展示用量说明。
3. 获取账号的模型列表，选择模型，测试连接并保存。授权成功不会自动把原 API Key 连接切换为 ChatGPT。新增或选择另一个账号也不会改变已保存的 AI 连接，需再次保存。
4. 可以新增其他账号或工作区连接；每个连接显示独立编号。重新登录会复用对应注册，不会把另一个账号的令牌写入原连接。
5. 「管理 ChatGPT 用量」可查看套餐或应用额度。退出连接时会尝试撤销远端可续期会话并清除本机令牌；若无法确认远端撤销，页面会提示到 ChatGPT 设置中断开应用。退出后仍保留本机设备标识及账号注册映射，供下次登录复用。

这是官方 Sign in with ChatGPT 的开放源代码客户端授权方式，官方文档说明套餐使用面向符合条件的开放源代码客户端及部分私有客户端，账号、客户端、地区、套餐和工作区权限仍以实际授权结果为准。本项目不更改仓库可见性，也不保证任意账号或私有客户端一定获准。

API Key 调用遵循 OpenAI API 的权限和计费；ChatGPT 套餐调用遵循用户明确授予的套餐权限及可用额度。两者的凭据不可互换，应用不会读取 Codex 或其他项目的登录信息。

## 本机存储和适用范围

- 模型连接写入 `backend/data/model-settings.private`，账号注册和令牌写入 `backend/data/chatgpt-accounts.private`。不写入浏览器 localStorage、业务数据库或源码；API 读取和保存响应均不返回原始密钥或令牌。
- Windows 文件使用当前用户的 DPAPI 加密；其他系统以仅文件所有者可读写的权限保存。配置使用原子替换，写入失败保留上次配置。Windows 换用户或换机器后需要重新配置、重新登录。
- 这是一台电脑上运行的个人应用，设置接口只允许本机来源，拒绝远端 Origin 和非本机 Host。后端应绑定 `127.0.0.1`；当前账号续期的互斥控制按单个后端进程设计，暂不适用于多用户、多进程服务部署。
- OAuth 回调监听临时的 `127.0.0.1` 端口，10 分钟后失效。每次登录使用独立 state、nonce、PKCE；验证签名、issuer、audience、过期时间、身份及授权范围后才替换账号凭据。可以在设置中取消本次登录。
- ChatGPT 套餐调用官方 `https://api.openai.com/v1/responses`，使用流式请求并关闭服务端存储，不使用 ChatGPT 网页内部接口。仅收到文字片段不能代表生成成功，必须收到明确完成事件。
- `backend/data/`、`*.private`、`.env`、数据库和 `references/` 都已排除在 Git 上传之外。私有文件备份应作为凭据保管。

## 常见提示

| 提示 | 处理方式 |
| --- | --- |
| 无法连接模型服务 | 检查 Base URL、网络、代理或本地服务是否启动 |
| 认证失败 / HTTP 401、403 | 检查此地址对应的 Key、模型权限；ChatGPT 可重新登录并授权 |
| HTTP 429 | 检查 API 额度或 ChatGPT 用量，稍后重试 |
| 模型列表不兼容 | 手动填写正确模型名，再测试连接 |
| 登录未完成 / 注册不完整 | 重新发起登录，确认客户端与账号处于官方开放范围 |
| 模型回复中途断开 | 记录保留，重新生成；不把未完成的片段当作成功回答 |

语音播放仍使用原来的语音服务，模型连接不提供语音识别或音频接口。

官方参考：

- [ChatGPT 客户端注册与授权](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [ChatGPT 账号与续期会话](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [模型目录与推理](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [套餐接口预览限制](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
- [OpenAI API 认证](https://developers.openai.com/api/reference/overview)
