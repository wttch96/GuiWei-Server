# 归位 · 智能收纳管理系统

一个「房间 → 多级容器 → 物品」的家庭收纳管理系统。后端提供完整 REST API，并把所有数据操作注册为 LangChain 工具交给 DeepSeek 调用；前端是 Vue 3 + Element Plus 管理后台。前后端分离，API 可直接复用于后续 iOS 客户端。

## 功能

- **房间 / 容器 / 物品三级收纳**：容器支持无限层级嵌套，物品可移动、搜索、借出/用完/丢弃等状态管理。
- **分类与标签**：每件物品有且只有一个大类，可拥有多个标签。
- **色系（可选）**：物品可标记黑色、白色、蓝色等色系，支持按色系筛选，也可在后台或 AI 对话中自定义取值。
- **AI 收纳助手**：自然语言查询与操作，例如「把电视遥控器放到客厅/电视柜/上层抽屉」「盘点一下书房」。AI 只能通过 28 个工具读写数据，所有改动真实落库并记录操作日志。回复支持 Markdown；涉及具体物品时以卡片展示图片、位置、分类、标签、数量与状态。
- **Token 统计**：每次模型调用都会记录输入/输出 token；工具调用展示所属轮次的 token 消耗，每条回复显示本轮合计，页面顶部显示当前会话累计，会话列表显示每个会话的总量。
- **会话管理**：会话列表可查看、切换、删除；「新建会话」立即开启独立上下文，历史会话仍保留在服务端。
- **拍照识物**：上传照片，经 DeepSeek 视觉模型（`deepseek-flash`）识别名称、描述、分类、标签、数量与建议位置，确认后一键入库。
- **以图找相似**：识图结果会立即与已有物品做本地描述匹配，按相似度展示「名称 / 分类 / 标签 / 描述」相近的物品，并在卡片上给出匹配原因，避免重复入库。
- **图片管理**：独立的文件管理页，可按文件名、关联状态筛选，查看占用空间、预览大图、下载、单张或批量删除已上传的图片。
- **管理后台**：概览统计、房间与容器树、物品筛选、分类/标签维护、AI 对话（Markdown 渲染、物品卡片、工具调用轨迹）、拍照识物、操作日志；支持手机浏览器访问与调用手机摄像头。
- **单管理员 + JWT**：管理员密码使用 werkzeug 加盐哈希存入数据库；登录后签发 Token，支持 `Authorization: Bearer`、`X-Auth-Token` 以及图片 URL 的 `?token=`。
- **文件存储**：图片按 `YYYY/MM` 分目录保存，UUID 文件名，数据库只存相对路径；访问图片需要 Token。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.11+、Flask 3、Flask-SQLAlchemy、SQLite、PyJWT、Pydantic 2、Pillow |
| AI | LangChain Core、langchain-deepseek（ChatDeepSeek）、手写 tool-calling 循环 |
| 视觉 | DeepSeek 多模态 `deepseek-flash`（OpenAI 兼容 `/chat/completions`） |
| 前端 | Vue 3、Vite 6、Element Plus、Pinia、Vue Router、Axios、dayjs |

## 目录结构

```text
guiwei-server/
├── backend/
│   ├── app/
│   │   ├── api/            # REST 接口（auth/rooms/containers/items/...）
│   │   ├── models/         # SQLAlchemy 模型
│   │   ├── services/       # 业务层，API 与 AI 工具共用
│   │   ├── tools/          # 28 个 LangChain @tool
│   │   ├── schemas/        # Pydantic 请求模型
│   │   ├── utils/          # 响应、认证、序列化、错误
│   │   ├── seed.py         # 演示数据
│   │   └── __init__.py     # 应用工厂、认证守卫、CLI
│   ├── tests/              # pytest（41 项）
│   ├── instance/           # SQLite 数据库（自动生成）
│   ├── uploads/            # 图片文件（自动生成）
│   ├── .env.example
│   ├── requirements.txt
│   └── run.py
└── frontend/
    ├── src/
    │   ├── api/            # Axios 接口封装
    │   ├── components/     # 物品表单等
    │   ├── layouts/        # 后台框架
    │   ├── stores/         # Pinia（登录态）
    │   ├── views/          # 概览、房间、物品、AI、识图、日志...
    │   └── utils/          # 日期、状态、图片 URL
    ├── vite.config.js      # 开发代理 /api → 127.0.0.1:5000
    └── package.json
```

## 快速开始

### 0. 一键启动脚本

根目录提供 Windows 与 Shell 两套脚本，会自动创建虚拟环境、安装依赖、生成 `.env`（若不存在）：

| 平台 | 后端 | 前端 |
| --- | --- | --- |
| Windows | 双击 `start-backend.bat` | 双击 `start-frontend.bat` |
| macOS / Linux / Git Bash | `./start-backend.sh` | `./start-frontend.sh` |

两个终端分别运行后端与前端，然后打开 `http://localhost:5173`。首次使用 Shell 脚本前可执行 `chmod +x start-*.sh`。手机访问方式见下文「手机访问与拍照」。

### 1. 后端（手动）

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt

# 首次运行：复制配置模板并修改密钥
# Windows: copy .env.example .env
# macOS/Linux: cp .env.example .env

python run.py
```

默认监听 `0.0.0.0:5000`（同一局域网内的手机也能访问），本机使用 `http://127.0.0.1:5000`。首次启动会自动建表，并按 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 创建管理员。仓库中若已存在本地生成的 `backend/.env`，默认账号为 `admin / admin123456`（仅用于本地开发，请登录后立即在右上角修改密码，或改 `.env` 后重新初始化）。

可选：写入演示数据（仅空库可用）。

```bash
python -m flask --app run.py seed-demo
```

### 2. 前端（手动）

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`，使用管理员账号登录。Vite 会把 `/api` 代理到 `http://127.0.0.1:5000`。

### 3. 手机访问与拍照

后端与 Vite 开发服务器默认监听 `0.0.0.0`，手机与电脑连接同一 Wi-Fi 即可访问：

1. 分别启动后端与前端。手机只需访问前端 `5173` 端口，`/api` 会由 Vite 代理到后端。
2. 查看电脑的局域网 IP：
   - Windows：`ipconfig`，找到「无线局域网适配器 WLAN」下的 IPv4 地址
   - macOS：`ipconfig getifaddr en0`
   - Linux：`hostname -I`
3. 手机浏览器打开 `http://<电脑IP>:5173`，用管理员账号登录。Vite 启动时也会打印 `Network:` 地址。
4. 拍照入口：
   - 「拍照识物」页点击「拍照」，手机会直接打开后置摄像头，拍完自动上传；已有照片时可点「重拍」。
   - 新增 / 编辑物品时，在照片区域点击「拍照」，现场拍摄后照片会随物品一起保存。
5. 手机打不开时：确认在同一局域网；Windows 防火墙允许 Node.js / Python（或放行 `5173`、`5000` 端口）；关闭路由器的访客网络 / AP 隔离。

安全提示：监听 `0.0.0.0` 适合家庭局域网调试，不要把 `5173` / `5000` 直接映射到公网。生产环境请使用 HTTPS、设置 `FLASK_DEBUG=false`，并修改默认密码与密钥。

### 4. 验证

```bash
curl http://127.0.0.1:5000/api/health
# {"code":0,"message":"ok","data":{"status":"ok","database":"ok",...}}
```

## 配置说明

所有配置通过 `backend/.env` 或环境变量提供，完整模板见 `.env.example`。

| 变量 | 说明 |
| --- | --- |
| `SECRET_KEY` / `JWT_SECRET` | Flask 与 JWT 密钥，生产环境必须修改 |
| `JWT_EXPIRES_HOURS` | Token 有效期，默认 168 小时 |
| `DATABASE_URL` | SQLAlchemy 连接串，留空时使用 `backend/instance/guiwei.db` |
| `UPLOAD_FOLDER` | 图片目录，默认 `backend/uploads` |
| `MAX_UPLOAD_MB` | 单张图片大小上限，默认 20 |
| `CORS_ORIGINS` | 允许的前端来源，逗号分隔 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 首次启动创建的管理员账号 |
| `DEEPSEEK_API_KEY` | DeepSeek 对话模型密钥；留空时 AI 对话返回 503 |
| `DEEPSEEK_API_BASE` / `DEEPSEEK_MODEL` | 默认 `https://api.deepseek.com` / `deepseek-flash` |
| `AI_MAX_ITERATIONS` | 单轮对话最多工具调用轮数，默认 8 |
| `VISION_API_BASE` / `VISION_API_KEY` / `VISION_MODEL` | 视觉识图覆盖项；默认复用 DeepSeek 的 Base/Key，模型为 `deepseek-flash` |
| `AUTO_CREATE_DB` / `AUTO_BOOTSTRAP_ADMIN` | 启动时自动建表 / 建管理员 |
| `FLASK_DEBUG` / `HOST` / `PORT` | 开发调试开关、监听地址与端口（`.env.example` 默认 `0.0.0.0:5000`，手机可经局域网访问；只想本机访问时改为 `127.0.0.1`） |
| `SERVE_FRONTEND` | 由 Flask 托管 `frontend/dist`（单机部署用） |

### AI 对话

在 `.env` 填入：

```dotenv
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-flash
```

重启后端后，后台「AI 收纳助手」即可使用。系统提示词要求模型：只通过工具操作、名称不唯一时先询问、删除操作必须显式 `confirm=true`、优先用 `move_item` 处理「把某物放到某处」。

### 拍照识图

DeepSeek 的 `deepseek-flash` 已支持图片输入，默认复用对话配置，无需额外设置：

```dotenv
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-flash
```

识图请求使用 OpenAI 兼容的 `POST https://api.deepseek.com/chat/completions`，图片以 base64 data URL 放在 `messages[].content` 的 `image_url` 块中，支持 JPEG / PNG / GIF / WebP（单图 ≤ 32 MiB）。

如需改用其它 OpenAI 兼容视觉网关，可单独覆盖：

```dotenv
VISION_API_BASE=https://your-gateway/v1
VISION_API_KEY=sk-...
VISION_MODEL=模型名称
```

`VISION_API_BASE` 会自动补 `/chat/completions`。未配置任何视觉密钥时，识图接口返回 503，但上传、关联、手动入库仍可正常使用。

### 以图找相似

识图完成后，后端会把视觉模型返回的名称、描述、分类、标签与图中文字拼成查询文本，与库中已有物品做本地文本匹配（不额外消耗模型调用）：

- 中文按二元组、英文/数字按单词切分，并过滤「一个」「物品」等无区分度的泛化词。
- 字段权重：名称 3.0、标签 2.0、分类 1.5、描述 1.0。
- 综合得分：`0.55 × 文本余弦 + 0.25 × 名称相似度 + 0.10 × 标签 Jaccard + 0.10 × 分类命中`，低于 `0.3` 的结果会被丢弃，默认返回前 6 个。
- 每个结果附带 `similarity`（0~1）与 `match_reasons`（如「名称相近」「同分类 · 电子产品」「共同标签：遥控器」）。
- 已关联到某物品的照片，会自动排除该物品本身。

`POST /api/photos/<id>/analyze` 的响应里直接包含 `similar_items`；物品数据变化后，可调用 `POST /api/photos/<id>/similar` 复用已保存的识图结果重新匹配，无需再次调用视觉模型。

```http
POST /api/photos/12/similar
Authorization: Bearer <token>
Content-Type: application/json

{"limit": 6}
```

### 图片管理

后台「图片管理」页面对应文件级接口，与物品关联无关：

```http
GET /api/photos?page=1&page_size=24&q=遥控器&status=attached&sort=newest
```

- `status`：`all`（默认）/ `attached` / `unattached`。
- `sort`：`newest`、`oldest`、`largest`、`smallest`。
- 响应在分页字段之外附带 `summary`：图片总数、总占用空间、未关联数量与占用空间；列表不返回识图全文以减小响应体。
- 下载使用 `GET /api/photos/<id>/file?download=1&token=<token>`，响应带 `Content-Disposition: attachment`。
- 批量删除使用 `POST /api/photos/batch-delete`，请求体 `{"ids":[1,2,3]}`（单次最多 200 张）；删除主图时会自动把该物品的下一张照片设为主图，并同步删除磁盘文件。

### 色系

物品的 `color_family` 是可选字符串（最长 20 字），建议值包括黑、白、灰、米、棕、红、橙、黄、绿、青、蓝、紫、粉、彩色、其他。创建/更新物品时传 `color_family` 即可，列表接口支持 `?color_family=黑色` 筛选，搜索关键词也会匹配色系。旧数据库启动时会自动补列（`ALTER TABLE items ADD COLUMN color_family ...`），无需手动迁移。

## Token 统计与会话

每次 `POST /api/ai/chat` 的响应都包含本轮与整个会话的 token 统计：

```json
{
  "usage": {
    "input_tokens": 13855,
    "output_tokens": 212,
    "total_tokens": 14067,
    "llm_calls": 3,
    "steps": [
      {"input_tokens": 4521, "output_tokens": 62, "total_tokens": 4583}
    ]
  },
  "session_usage": {"input_tokens": 28612, "output_tokens": 447, "total_tokens": 29059, "llm_calls": 6}
}
```

- 每次工具调用循环中的模型请求都会读取 LangChain 的 `usage_metadata`（兼容 `response_metadata.token_usage`），累加到本轮统计。
- `tool_calls` 中每一项额外带有 `step`（第几轮模型调用）与 `usage`（该轮消耗），方便定位 token 主要花在哪一步。
- 历史消息通过 `GET /api/ai/sessions/<id>/messages` 返回，assistant 消息上的 `usage` 即该轮统计。
- `GET /api/ai/sessions` 返回会话列表：标题（首条用户消息）、预览、消息数、创建/更新时间与累计 token。
- `DELETE /api/ai/sessions/<id>` 删除该会话的全部消息；前端「新建会话」只是切换到新的 `session_id`，不会删除旧会话。
- 旧数据库启动时会自动执行 `ALTER TABLE ai_messages ADD COLUMN usage ...`，历史消息的 token 记为 0，不影响继续使用。

## AI 工具（28 个）

| 领域 | 工具 |
| --- | --- |
| 房间 | `list_rooms`、`create_room`、`update_room`、`delete_room` |
| 容器 | `list_containers`、`create_container`、`update_container`、`move_container`、`delete_container` |
| 物品 | `search_items`、`get_item`、`create_item`、`update_item`、`move_item`、`set_item_tags`、`delete_item`、`list_item_photos` |
| 分类 | `list_categories`、`create_category`、`update_category`、`delete_category` |
| 标签 | `list_tags`、`create_tag`、`update_tag`、`delete_tag` |
| 照片 / AI | `recognize_photo` |
| 查询 | `inventory_overview`、`global_search` |

工具统一返回 JSON：成功 `{"ok":true,"data":...}`，失败 `{"ok":false,"error":"...","status":409}`。删除类工具必须传 `confirm=true`。AI 产生的写操作日志 `source` 为 `ai`，后台操作则为 `api`。

## API 概览

统一响应：`{"code":0,"message":"ok","data":...}`；错误时 HTTP 状态码与 `code` 一致，`data` 可为 `null` 或候选列表。分页数据位于 `data.items/total/page/page_size`。

除 `POST /api/auth/login` 与 `GET /api/health` 外，所有接口都需要 Token：

```http
Authorization: Bearer <token>
```

图片文件还支持 `?token=<token>` 便于 `<img src>` 直接加载。

| 模块 | 接口 |
| --- | --- |
| 认证 | `POST /api/auth/login`、`GET /api/auth/me`、`POST /api/auth/change-password` |
| 房间 | `GET/POST /api/rooms`、`GET/PUT/DELETE /api/rooms/<id>`、`GET /api/rooms/<id>/tree` |
| 容器 | `GET/POST /api/containers`、`GET/PUT/DELETE /api/containers/<id>`、`GET /api/containers/tree`、`POST /api/containers/<id>/move` |
| 物品 | `GET/POST /api/items`、`GET/PUT/DELETE /api/items/<id>`、`POST /api/items/<id>/move` |
| 分类 | `GET/POST /api/categories`、`PUT/DELETE /api/categories/<id>` |
| 标签 | `GET/POST /api/tags`、`PUT/DELETE /api/tags/<id>` |
| 照片 | `POST /api/photos`（multipart）、`GET /api/photos`（分页；带 `item_id` 时返回数组）、`GET /api/photos/<id>/file`（`download=1` 强制下载）、`POST /api/photos/<id>/attach`、`POST /api/photos/<id>/primary`、`DELETE /api/photos/<id>`、`POST /api/photos/batch-delete`、`POST /api/photos/<id>/analyze`、`POST /api/photos/<id>/similar` |
| AI | `POST /api/ai/chat`、`GET /api/ai/status`、`GET /api/ai/tools`、`GET /api/ai/sessions`、`GET /api/ai/sessions/<id>/messages`、`DELETE /api/ai/sessions/<id>` |
| 其它 | `GET /api/stats/overview`、`GET /api/search?q=`、`GET /api/logs`、`GET /api/health` |

### 示例

登录：

```bash
curl -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123456"}'
```

创建物品（可直接用名称解析房间、容器路径、分类和标签）：

```bash
curl -X POST http://127.0.0.1:5000/api/items \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "电视遥控器",
    "room_name": "客厅",
    "container_path": "电视柜/上层抽屉",
    "category_name": "电子产品",
    "tag_names": ["常用"],
    "quantity": 1
  }'
```

AI 对话：

```bash
curl -X POST http://127.0.0.1:5000/api/ai/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"把电视遥控器放到卧室/衣柜/顶部收纳盒"}'
```

响应包含 `session_id`、`reply`、`tool_calls`（每一步的工具名、参数和结果）与 `cards`（从工具结果提取的物品卡片，最多 8 张）。`reply` 为 Markdown 文本；带上同一个 `session_id` 可继续多轮对话，历史消息也会返回对应的 `cards`。

## 数据模型与删除策略

- `Room 1—N Container`，`Container.parent_id` 自关联实现多级嵌套。
- `Item` 通过 `room_id`、`container_id` 定位，通过 `category_id` 关联唯一分类，通过 `item_tags` 关联多个标签。
- `Photo.item_id` 可空：照片可以先上传、后关联；删除物品时级联删除照片记录并清理磁盘文件。
- 删除房间：房间内必须没有容器和物品，否则返回 409。
- 删除容器：必须没有子容器和物品，否则返回 409。
- 删除分类：该分类下物品变为未分类，分类本身删除。
- 删除标签：自动从所有物品上解绑。
- 移动容器：整棵子树及其中的物品一起迁移房间。
- 所有写操作都会写入 `operation_logs`，可在后台「操作日志」查看。

## 图片存储

- 仅接受 JPG / PNG / WEBP / GIF（使用 Pillow 实际解码校验，不信任扩展名）。
- 文件名使用 UUID，按 `uploads/YYYY/MM/` 分目录。
- 数据库保存相对路径，下载时校验路径必须位于上传目录内，防止目录穿越。
- 单张图片默认上限 20MB，可通过 `MAX_UPLOAD_MB` 调整。
- 图片下载需要 Token；前端通过 `photoUrl()` 自动拼接 `?token=`。

## 生产部署

### 单机（Flask 托管前端）

```bash
cd frontend
npm run build

cd ../backend
# .env 中设置：
#   SERVE_FRONTEND=true
#   AUTO_CREATE_DB=false
#   FLASK_DEBUG=false
pip install waitress
waitress-serve --host 0.0.0.0 --port 5000 run:app
```

访问 `http://<服务器>:5000`。若部署在公网，请务必修改 `SECRET_KEY`、`JWT_SECRET` 与管理员密码，并在 HTTPS 反向代理后运行。

### 前后端分开

- 前端 `dist` 交给 Nginx / CDN。
- Nginx 将 `/api/` 与 `/uploads/` 反代到 Flask。
- 在 `CORS_ORIGINS` 中填写前端域名。

## 测试

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

测试使用临时 SQLite 与临时上传目录，不会污染开发数据。覆盖认证、房间/容器/物品 CRUD、色系属性、照片上传与主图切换、图片库分页与批量删除、AI 工具调用、AI 对话循环、token 统计与会话管理、识图结果解析、识图后的相似物品匹配等。

## iOS 迁移说明

后端是 API-first 的，iOS 端只需要：

1. `POST /api/auth/login` 获取 JWT，后续请求带 `Authorization: Bearer`。
2. 使用与后台完全相同的 JSON 接口；字段命名已统一为 snake_case。
3. 图片展示使用 `/api/photos/<id>/file?token=<token>`（或自行带 Header 下载）。
4. 拍照上传使用 multipart `file`，可选 `item_id`；识图调用 `POST /api/photos/<id>/analyze`，响应中的 `similar_items` 可直接用于「是否已有类似物品」的提示，也可稍后调用 `POST /api/photos/<id>/similar` 重新匹配。
5. AI 对话调用 `POST /api/ai/chat`，保存返回的 `session_id` 即可继续上下文；响应中的 `usage` / `session_usage` 可直接展示 token 消耗，会话列表与删除使用 `/api/ai/sessions`。

## 常见问题

- **AI 对话返回 503**：未配置 `DEEPSEEK_API_KEY`。
- **识图返回 503**：未配置 `DEEPSEEK_API_KEY`，且 `VISION_API_KEY` 也为空。`deepseek-flash` 已支持图片，通常只需填写 DeepSeek 密钥。
- **上传返回 413**：图片超过 `MAX_UPLOAD_MB`。
- **iPhone 照片上传失败**：目前仅支持 JPG / PNG / WEBP / GIF。请直接用系统相机拍照（通常输出 JPEG），或在「设置 → 相机 → 格式」中选择「兼容性最佳」；HEIC 照片需先转换为 JPG。
- **图片打不开**：图片接口需要 Token，确认 URL 带 `?token=` 或请求头。
- **忘记管理员密码**：在 backend 目录执行 `python -m flask --app run.py reset-password --username admin --password 新密码`。
- **没有管理员账号**：执行 `python -m flask --app run.py create-admin --username admin --password 新密码`，或在 `.env` 设置后重启。

## 安全建议

- 不要提交 `.env`、数据库、上传目录（已在 `.gitignore` 中忽略）。
- 首次登录后修改默认密码；生产环境关闭 `AUTO_BOOTSTRAP_ADMIN`。
- 使用 HTTPS；若由 Nginx 终止 TLS，Flask 仅监听内网地址。
- 定期备份 `backend/instance/guiwei.db` 与 `backend/uploads/`。
