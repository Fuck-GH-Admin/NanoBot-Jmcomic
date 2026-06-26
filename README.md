# NanoBot-Jmcomic - 禁漫下载QQ机器人

基于 [NoneBot2](https://github.com/nonebot/nonebot2) + [jmcomic](https://github.com/hect0x7/JMComic-Crawler-Python/) 的禁漫下载QQ机器人插件，使用 [LLOneBot](https://github.com/LLOneBot/LLOneBot) 作为QQ机器人框架。

## 注意

**本项目不是标准 NoneBot2 插件格式**，而是直接在 `src/plugins/chatbot` 目录下开发的业务插件。使用时需要将整个 `Jmbot` 目录作为工作目录，而非通过 `nb plugin install` 安装。

## 功能

- **JM下载**：通过 `/jm 本子号` 指令下载禁漫本子
- **系列本检测**：自动检测系列本并提供关联章节ID（最多显示50个）
- **PDF加密**：下载的本子自动转换为加密PDF（密码：114514）
- **流式处理**：边下边转换边发，并发限制为3
- **文件校验**：小于10KB的文件视为无效，自动跳过
- **发送重试**：发送失败自动重试最多2次
- **输入去重**：重复ID自动去重
- **防重复下载**：本地已存在的本子跳过下载
- **苦命鸳鸯彩蛋**：发送"苦命鸳鸯"自动下载特定本子
- **启动清理**：每次启动自动清空临时目录

## 目录结构

```
Jmbot/
├── bot.py                       # NoneBot2 启动入口
├── .env                         # NoneBot2 配置
├── option.yml                   # jmcomic 下载配置
├── config_bot_base.yaml         # 机器人业务配置
├── pytest.ini                   # pytest 配置
├── tests/
│   ├── conftest.py              # 测试共享夹具
│   ├── test_string_utils.py     # 字符串工具测试
│   ├── test_book_repo.py        # 仓库层测试
│   ├── test_config.py           # 配置管理测试
│   └── test_book_service.py     # 业务服务测试
└── src/
    └── plugins/
        └── chatbot/
            ├── __init__.py      # 插件初始化 + 启动清理
            ├── config.py        # 配置管理（含热更新）
            ├── consts.py        # 常量定义
            ├── matchers/
            │   ├── group_chat.py    # 群聊处理器
            │   └── private_chat.py  # 私聊处理器
            ├── services/
            │   ├── book_service.py         # 下载/转换/加密/发送核心
            │   └── permission_service.py   # 权限管理
            ├── repositories/
            │   └── book_repo.py # 书籍文件仓储
            └── utils/
                ├── pdf_utils.py     # ZIP→PDF 转换
                └── network_utils.py # 网络检测工具
```

## 安装依赖

```bash
pip install nonebot2 nonebot-adapter-onebot fastapi
pip install jmcomic pycryptodome
pip install PyPDF2 img2pdf Pillow
pip install pydantic-settings watchdog pyyaml
pip install requests
```

## 配置说明

**重要：配置文件不会被git跟踪，需要手动创建！**

### 1. 复制示例配置文件

```bash
copy .env.example .env
copy option.yml.example option.yml
copy config_bot_base.yaml.example config_bot_base.yaml
```

### 2. 修改配置文件

#### .env（NoneBot2配置）

```ini
SUPERUSERS=["你的QQ号"]
NICKNAME=["机器人昵称"]
DRIVER=~fastapi
HOST=127.0.0.1
PORT=8080
ONEBOT_V11_WS_URL=ws://127.0.0.1:8080/onebot/v11/ws
ONEBOT_V11_ACCESS_TOKEN="你的Token"
LOG_LEVEL=DEBUG
API_TIMEOUT=60.0
```

#### option.yml（jmcomic下载配置）

```yaml
dir_rule:
  base_dir: D:\你的路径\本子保存目录

client:
  postman:
    meta_data:
      proxies:
        http: http://127.0.0.1:7890
        https: http://127.0.0.1:7890
```

#### config_bot_base.yaml（业务配置）

```yaml
jm_download_dir: data/jm_temp
jm_option_path: option.yml
books_folder: D:\你的路径\本子保存目录
font_path: C:\Windows\Fonts\msyh.ttc
```

## 使用方法

### 1. 启动机器人

```bash
cd Jmbot
python bot.py
```

### 2. 配置LLOneBot

在LLOneBot中配置WebSocket客户端（反向）：
- URL：`ws://127.0.0.1:8080/onebot/v11/ws`
- Access Token：与`.env`中配置一致

### 3. 使用指令

**群聊：**
```
/jm 350234          # 下载单个本子
/jm 350234 350235   # 下载多个本子
@bot /jm 350234     # @机器人也可以
```

**私聊：**
```
/jm 350234
jm 350234           # 私聊也支持 jm 开头
下载本子 350234
禁漫 350234
```

**特殊功能：**
```
苦命鸳鸯            # 触发彩蛋，自动下载 350234 和 350235
```

## 运行测试

```bash
cd Jmbot
python -m pytest tests/ -v
```

## 功能特性

### 流式处理

每个本子独立处理，边下载边转换边发送。并发上限3个，避免资源耗尽。

### 系列本检测

下载系列本时，自动检测并发送关联章节ID列表（最多50个，排除已请求的ID）：
```
📚 系列本关联章节ID：
350235, 350236, 350237
```

### PDF处理

- 自动将下载的图片打包为PDF
- 注入随机UUID元数据，确保每次生成的PDF MD5不同
- 使用PyPDF2加密，密码：`114514`
- 小于10KB的文件视为无效下载，自动跳过

### 发送重试

文件发送最多重试2次，超时时间根据文件大小动态计算（50KB/s基准）。

### 防重复下载

下载前先检查本地是否已存在相同ID的本子，避免重复下载。

### 启动清理

每次启动时自动清空临时下载目录 `data/jm_temp`。

## 常见问题

### Q: WebSocket连接403 Forbidden

A: 检查LLOneBot的Access Token是否与`.env`中配置一致。

### Q: 下载失败

A: 检查`option.yml`中的代理配置和网络连通性。jmcomic库会自动更新API域名。

### Q: PDF文件名显示为编号

A: 正常情况下会显示本子标题，如果显示为编号可能是API获取标题失败。

## 开发说明

本项目**不是标准NoneBot2插件格式**，有以下特点：

1. 直接在 `src/plugins/chatbot` 目录下开发
2. 使用 `nonebot.load_plugin("src.plugins.chatbot")` 加载
3. 配置文件直接放在项目根目录
4. 不支持通过 `nb plugin install` 安装

如需修改或扩展功能，请直接编辑 `src/plugins/chatbot` 目录下的文件。

## License

MIT
