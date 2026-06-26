# 架构文档

## 项目概述

NanoBot-Jmcomic 是一个基于 NoneBot2 + jmcomic 的 QQ 机器人，专注于禁漫本子下载。用户通过 QQ 群聊或私聊发送 `/jm 本子号` 指令，机器人自动完成下载、PDF 转换、加密、发送全流程。

## 架构分层

```
┌──────────────────────────────────────────────────────┐
│                     Matcher 层                         │
│    group_chat.py  /  private_chat.py                  │
│    (消息匹配 & 路由)                                    │
├──────────────────────────────────────────────────────┤
│                    Service 层                          │
│    book_service.py  /  permission_service.py           │
│    (业务逻辑编排)                                       │
├──────────────────────────────────────────────────────┤
│                  Repository 层                         │
│    book_repo.py                                       │
│    (文件系统抽象)                                       │
├──────────────────────────────────────────────────────┤
│                    Utils 层                            │
│    pdf_utils.py  /  network_utils.py  /  string_utils.py│
│    (工具函数)                                          │
├──────────────────────────────────────────────────────┤
│                     Config 层                          │
│    config.py  /  consts.py                             │
│    (配置管理 & 常量)                                    │
└──────────────────────────────────────────────────────┘
```

## 模块职责

### Matcher 层 — 消息路由

| 模块 | 职责 |
|------|------|
| `matchers/group_chat.py` | 群聊消息处理，优先级10，`block=False`。去掉 `[CQ:at,...]` 后匹配 `/jm 数字` 格式 |
| `matchers/private_chat.py` | 私聊消息处理，优先级1，`block=True`。匹配 `/jm`、`jm`、`下载本子`、`禁漫` 等前缀 |

**群聊 VS 私聊差异：**

| 特性 | 群聊 | 私聊 |
|------|------|------|
| 触发格式 | 严格 `/jm 数字` | 多种前缀 |
| 是否需要 @ | 不需要 | N/A |
| 权限 | 所有群成员 | 所有用户 |

### Service 层 — 业务逻辑

#### BookService

`services/book_service.py` 是核心服务，负责协调下载、转换、加密、发送全流程。

**handle_jm_download(ids) 流程：**

```
输入 ID 列表
    │
    ├─ 去重（保持顺序）
    ├─ 发送"处理中"消息
    ├─ 并发下载（semaphore=3）
    │   └─ 每个 ID：
    │       ├─ check_env → 环境检查
    │       ├─ _sync_download_single
    │       │   ├─ 系列本检测 → 收集关联 ID
    │       │   ├─ 本地查重 → 已存在则跳过下载
    │       │   ├─ jmcomic 下载 → 章节文件夹
    │       │   └─ 打包 ZIP
    │       ├─ 文件校验（<10KB 跳过）
    │       ├─ ZIP → PDF 转换
    │       ├─ PDF 加密（密码 114514）
    │       └─ 发送文件（最多重试 2 次）
    │
    ├─ 发送系列本关联 ID 列表（最多 50 个）
    └─ 返回汇总结果
```

#### PermissionService

`services/permission_service.py` 权限管理。超级用户从 NoneBot2 配置读取（`.env` 的 `SUPERUSERS`），群聊不限制，私聊开放所有用户。

### Repository 层 — 文件抽象

`repositories/book_repo.py` 封装文件系统操作：

| 方法 | 用途 |
|------|------|
| `get_all_books()` | 扫描书架目录所有支持格式的文件 |
| `find_book_by_id_or_name(id)` | 按 ID 或名称模糊查找本地文件 |
| `get_pdf_output_path(source)` | 生成 PDF 输出路径 |
| `get_zip_save_path(title)` | 生成 ZIP 保存路径 |

路径规则：
- 书架目录：`{books_folder}/`
- 输出目录：`{books_folder}/output/`
- ZIP 保存：`{books_folder}/{title}.zip`
- PDF 输出：`{books_folder}/output/{name}.pdf`

### Utils 层 — 工具函数

| 模块 | 功能 |
|------|------|
| `pdf_utils.py` | ZIP 解压 → 图片处理（Pillow resize + JPEG）→ img2pdf 组装 |
| `network_utils.py` | 网络连通性检测（当前未在下载流程中调用） |
| `string_utils.py` | 文本清洗、莱文斯坦距离、模糊匹配 |

### Config 层 — 配置管理

`config.py` 的 ConfigManager 负责从 `config_bot_base.yaml` 加载配置，支持 watchdog 热更新：

```
ConfigManager
    ├── Config (pydantic model) — 类型定义
    ├── load_config() — 从 YAML 读取并做类型转换
    ├── _start_watcher() — watchdog 文件监控
    └── plugin_config — 全局单例
```

配置优先级：`config_bot_base.yaml` > pydantic 默认值。

## 数据流

```
用户输入 /jm 350234
    │
    ▼
group_chat.py → 正则匹配 → 提取数字 ID
    │
    ▼
book_service.handle_jm_download()
    │
    ├─ 环境检查 (jmcomic + option.yml)
    ├─ ID 去重
    ├─ asyncio.gather(semaphore=3)
    │   └─ 每个 ID:
    │       ├─ _sync_download_single()
    │       │   ├─ jmcomic.JmDownloader.download_album()
    │       │   ├─ 系列本检测 (album.episode_list)
    │       │   ├─ ZIP 打包
    │       │   └─ 返回 [{path, title, series_ids}]
    │       │
    │       ├─ 文件校验 (>10KB?)
    │       ├─ PDFUtils.convert_zip_to_pdf()
    │       ├─ _encrypt_pdf_task(password="114514")
    │       │   └─ PyPDF2: 复制页面 + 注入 UUID 元数据 + 加密
    │       │
    │       └─ bot.call_api("upload_group_file", ...)
    │           └─ 重试最多 2 次
    │
    └─ 返回汇总消息
```

## 关键设计决策

### 1. 非标准插件格式

直接在 `src/plugins/chatbot` 下开发，通过 `nonebot.load_plugin("src.plugins.chatbot")` 加载。这样做的好处是开发迭代快，不需要每次改代码都重新安装插件。

### 2. 流式处理而非批处理

每个本子独立处理（下载→转换→加密→发送），而不是全部下完再统一处理。配合 `asyncio.Semaphore(3)` 控制并发数，避免资源耗尽。

### 3. 全局单例模式

Service 和 Repository 层通过模块级单例共享状态：

```
services/__init__.py
    book_srv = BookService()   # 全局唯一实例
    perm_srv = PermissionService()
```

其他模块通过 `from ..services import book_srv` 引用。

### 4. 配置热更新

ConfigManager 使用 watchdog 监控 `config_bot_base.yaml` 文件变化，修改后自动重载，无需重启。

### 5. 去重策略

- **输入去重**：`list(dict.fromkeys(ids))` 保持顺序去重
- **系列本去重**：排除已在请求列表中的 ID，避免重复
- **本地去重**：下载前检查 `books_dir` 是否已有同名文件

### 6. 安全性

- PDF 统一加密（密码 `114514`）
- 注入随机 UUID 元数据，防指纹追踪
- 配置文件（`.env`, `config_bot_base.yaml`, `option.yml`）被 gitignore，不跟踪到仓库

## 测试架构

```
tests/
├── conftest.py              # 测试环境初始化
│   ├─ 创建临时工作目录
│   ├─ 生成测试配置文件
│   ├─ 初始化 NoneBot
│   └─ mock_bot fixture
│
├── test_string_utils.py     # 纯函数测试（无外部依赖）
├── test_book_repo.py        # 文件系统操作测试
├── test_config.py           # 配置加载/热更新测试
└── test_book_service.py     # 业务逻辑测试（mock jmcomic & Bot）
```

测试策略：
- **纯逻辑层**：直接测试，无需 mock（string_utils）
- **文件系统层**：依赖 tmp_path，每次测试独立文件环境
- **配置层**：依赖临时 YAML 文件，测试热加载逻辑
- **服务层**：patch jmcomic、PdfReader/PdfWriter、Bot API，验证流程正确性

## 依赖关系

```
bot.py
  └─ src.plugins.chatbot (nonebot.load_plugin)
       ├─ config.py → pyyaml, pydantic, watchdog
       ├─ matchers/group_chat.py → services/book_service
       ├─ matchers/private_chat.py → services/book_service
       ├─ services/book_service.py
       │    ├─ repositories/book_repo.py
       │    ├─ utils/pdf_utils.py → Pillow, img2pdf
       │    ├─ utils/network_utils.py → requests
       │    └─ jmcomic (外部库)
       └─ services/permission_service.py → nonebot 配置
```

## 并发模型

```
主协程 (asyncio)
  └─ 发送"处理中"消息
  └─ asyncio.gather(*tasks)
       └─ Semaphore(3)
            └─ process_and_send_single(id)
                 ├─ run_in_executor → _sync_download_single (线程池)
                 ├─ run_in_executor → PDFUtils.convert_zip_to_pdf (线程池)
                 ├─ run_in_executor → _encrypt_pdf_task (线程池)
                 └─ await bot.call_api → 发送文件 (IO)
```

所有 CPU 密集型操作（jmcomic 下载、图片处理、PDF 加密）通过 `run_in_executor` 委托到线程池执行，避免阻塞事件循环。
