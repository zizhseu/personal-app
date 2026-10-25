# 内容来源与采集适配（2026-10-25）

## 使用

在「设置 → 内容采集来源」选择小红书的采集方式，点击「连接与登录」。两种方式分别扫码、分别保管登录记录，切换不会复制 Cookie、删除资料或重新生成 AI 报告。

登录记录持久保存在本机，关闭页面或重启应用不会主动清除。打开连接弹窗会自动检查已有登录，确认有效后直接使用，无需每次扫码。CLI 在有效登录检查、搜索和读取后保存服务端返回的 Cookie，保留平台轮换后的凭据；临时网络错误或访客响应不会覆盖原登录记录。

本项目没有按固定天数清除登录的机制，实际有效期由小红书服务端决定，无法承诺固定维持几天。平台判定会话失效、撤销登录或要求验证时，仍需重新登录或完成验证。下文的「搜索引用有效期 30 分钟」仅约束搜索结果的访问参数，不是登录有效期。

| 方式 | 搜索与读取 | 排序 | 时间筛选 |
| --- | --- | --- | --- |
| 浏览器采集（MCP） | 原有本机 xiaohongshu-mcp 服务 | 综合、最新、最多点赞、最多收藏 | 不限、一天内、一周内、半年内 |
| 接口采集（CLI） | xiaohongshu-cli 0.6.4 的 Python 客户端；扫码时使用独立浏览器 | 综合、最新、热度 | 不限 |

新搜索使用已保存的方式；已有结果保留原采集器和私有访问参数，采集时不跟随新选择。MCP 连接地址或令牌更换、CLI 登录账号更换后，需要重新搜索相关旧结果。相同平台、相同原始内容 ID 始终只保存一份资料。

首次使用 CLI 时点击「安装采集组件」，也可在项目专用 conda 环境中安装 `backend/requirements-collectors.txt`。依赖固定为 `xiaohongshu-cli==0.6.4`、`camoufox==0.5.8`；不依赖 Git 忽略的 `references/` 检出目录。没有调用 CLI 的发帖、评论、关注等写操作，也不会自动提取系统浏览器 Cookie。

## 分层

```text
搜索页面／设置页面
  → 来源服务 sources/service.py
  → 注册表 sources/registry.py
  → SourceProvider：MCP、CLI，或其他平台的适配器
  → CollectedMaterial：来源、原文、图片等统一材料
  → 现有去重入库 → OCR → 校对 → AI 整理 → 确认加入问答
```

- `sources/contracts.py`：平台、能力、搜索定位信息及统一材料格式。
- `sources/registry.py`：受控注册与默认选择，不接受用户提供的执行命令或任意导入路径。
- `sources/service.py`：筛选能力检查、搜索引用加密保存、结果归属和统一材料校验。
- `sources/mcp.py`：包装已有浏览器采集流程，保留连接与启动方式。
- `sources/cli.py`：CLI 数据规范化与子进程管理。
- `sources/cli_worker.py`：在独立进程内调用固定 SDK，用标准输入传递读取参数，避免访问参数出现在命令行中；登录凭据使用项目私有存储。
- `sources/assets.py`：按平台声明的图片域名及 Referer 下载，跳转也重新校验。

搜索引用有效期为 30 分钟，最多保留 160 个；响应只包含展示字段和随机结果 ID，不包含笔记访问令牌。界面最多选 5 条逐条采集。采集失败不会自动换成另一种方式，用户可以明确切换后重新搜索。

## 接口

统一入口在 `/api/experiences` 下：

| 接口 | 用途 |
| --- | --- |
| `GET /sources` | 平台、可选实现、当前选择和能力 |
| `PUT /sources/{platform}` | 保存 `{providerId}`，只允许已注册项 |
| `GET/PUT /sources/{platform}/{provider}/connection` | 读取或保存此实现的连接配置 |
| `POST /sources/{platform}/{provider}/start` | 准备组件 |
| `GET /sources/{platform}/{provider}/start-status` | 准备进度 |
| `GET /sources/{platform}/{provider}/login` | 此实现的登录状态 |
| `POST /sources/{platform}/{provider}/login/qrcode` | 此实现的扫码登录 |
| `POST /search` | `{platform, keyword, sort, period}`，平台默认小红书 |
| `POST /collect` | `{resultId}`，使用结果绑定的采集器 |

原 `/connection`、`/login` 等 MCP 专用端点保留兼容旧客户端；新版页面使用来源专属接口。所有端点继续要求本机来源。

## 接入新平台

1. 明确合法可用的搜索、内容获取与登录方式，完成独立的真实验证。
2. 在 `sources/` 新建适配器，实现 `SourceProvider`，返回统一搜索结果和 `CollectedMaterial`。访问令牌等参数只放在 `SearchResult.locator` 中。
3. 声明排序、时间筛选、图片、字幕、扫码与组件安装能力。界面根据能力提供选项，服务端再次校验。
4. 创建 `Platform`，声明该平台的图片域名及 Referer，在注册表中调用 `register()`；不需要在面经页面编写平台判断分支。
5. 添加样例响应、错误、凭据隔离、过期、去重与图片跳转测试。视频来源应由适配器先提取可用字幕或转录并保留时间信息，再进入材料整理。

当前只注册小红书的 MCP 和 CLI；知乎、B 站没有被标为已支持，也没有在本次实现其采集。

## 本机存储与组件来源

- `backend/data/experience-sources.private`：各平台默认实现。
- `backend/data/experience-results.private`：绑定平台和实现的有效搜索引用。
- `backend/data/experience-cli-cookies.private`、`experience-cli-session.private`：独立 CLI 登录与会话标识。
- `backend/data/experience-cli-qr.private`、`experience-cli-install.private`：二维码和准备状态。
- `backend/data/xhs-cli/`：CLI 独立状态；`.runtime/xhs-cli/`：本项目复用的浏览器二进制。

私有文档沿用 Windows 当前用户 DPAPI 和原子写入，不在接口中回填 Cookie；以上本机数据继续排除在 Git 外。旧 MCP 的连接、Cookie 和资料不迁移给 CLI。

Windows 扫码浏览器固定为 [Camoufox v156.0.1-beta.36](https://github.com/daijro/camoufox/releases/tag/v156.0.1-beta.36) 的 `win.x86_64.zip`，使用官方发布页的 SHA256 `096fd4832a7a32f2aa7f7bdd07fe6253dda296cbe783acd7bc2c86cf5ae62031` 校验，避免依赖被限流的公共 releases API。CLI 项目见 [jackwener/xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli)。
