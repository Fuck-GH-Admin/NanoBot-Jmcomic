# Jmbot - 禁漫下载QQ机器人

基于 NoneBot2 + jmcomic 库的禁漫下载QQ机器人插件。

## ⚠️ 注意

**本项目不是标准 NoneBot2 插件格式**，而是直接在 `src/plugins/chatbot` 目录下开发的业务插件。使用时需要将整个 `Jmbot` 目录作为工作目录，而非通过 `nb plugin install` 安装。

## 功能

- 📥 **JM下载**：通过 `/jm 本子号` 指令下载禁漫本子
- 📚 **系列本检测**：自动检测系列本并提供关联章节ID
- 🔄 **自动代理切换**：裸连不可用时自动切换到代理模式
- 🔒 **PDF加密**：下载的本子自动转换为加密PDF（密码：114514）
- 🎭 **苦命鸳鸯彩蛋**：发送"苦命鸳鸯"自动下载特定本子

## 目录结构

```
Jmbot/
├── bot.py                  # NoneBot2 启动入口
├── .env                    # NoneBot2 配置
├── option.yml              # jmcomic 下载配置
├── config_bot_base.yaml    # 机器人业务配置
└── src/
    └── plugins/
        └── chatbot/
            ├── __init__.py         # 插件初始化
            ├── config.py           # 配置管理
            ├── consts.py           # 常量定义
            ├── matchers/
            │   ├── group_chat.py   # 群聊处理器
            │   └── private_chat.py # 私聊处理器
            ├── services/
            │   ├── book_service.py         # 下载核心逻辑
            │   └── permission_service.py   # 权限管理
            ├── repositories/
            │   └── book_repo.py    # 书籍文件管理
            └── utils/
                ├── pdf_utils.py    # PDF转换工具
                └── network_utils.py # 网络连通性检测
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

### .env（NoneBot2配置）

```ini
SUPERUSERS=["你的QQ号"]
NICKNAME=["机器人昵称"]
COMMAND_START=["/", ""]
DRIVER=~fastapi
HOST=127.0.0.1
PORT=8080
ONEBOT_V11_ACCESS_TOKEN="你的Token"
LOG_LEVEL=DEBUG
```

### option.yml（jmcomic下载配置）

```yaml
client:
  domain:
    api:
      - www.cdnhth.club
      - www.cdngwc.cc
  impl: api
  postman:
    meta_data:
      headers:
        User-Agent: Mozilla/5.0 ...
    type: curl_cffi
  retry_times: 5
  timeout: 30

dir_rule:
  base_dir: D:\文件\学习资料\本  # 本子保存目录
  rule: Bd / {Aid}_{Pid}_{Pindex}_{Ptitle}

download:
  image:
    decode: true
    suffix: .png
  threading:
    image: 20
```

### config_bot_base.yaml（业务配置）

```yaml
jm_download_dir: data/jm_temp     # 临时下载目录
jm_option_path: option.yml        # jmcomic配置路径
books_folder: D:\文件\学习资料\本  # 本子保存目录
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
/jm 350234          # 直接发送即可
```

**特殊功能：**
```
苦命鸳鸯            # 触发彩蛋，自动下载特定本子
```

## 功能特性

### 自动代理切换

首次下载时自动检测网络连通性：
- 裸连可用 → 禁用代理，直接连接
- 裸连不可用 → 自动启用 `127.0.0.1:7890` 代理

### 系列本检测

下载系列本时，自动检测并发送关联章节ID列表：
```
📚 检测到系列本，关联章节ID：
350235, 350236, 350237
```

### PDF处理

- 自动将下载的图片打包为PDF
- 注入随机UUID元数据，确保每次生成的PDF MD5不同
- 使用PyPDF2加密，密码：`114514`

### 防重复下载

下载前检查本地是否已存在相同ID的本子，避免重复下载。

### 启动清理

每次启动时自动清空临时下载目录 `data/jm_temp`。

## 配套QQ机器人框架

本项目使用 [LLOneBot](https://github.com/LLOneBot/LLOneBot) 作为QQ机器人框架，需要配合 NoneBot2 使用。

## 常见问题

### Q: WebSocket连接403 Forbidden

A: 检查LLOneBot的Access Token是否与`.env`中配置一致。

### Q: 下载失败

A: 检查`option.yml`中的API域名是否可用，可能需要更新域名列表。

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
