# 全栈工程测评 · 交付仓库

本仓库是本次测评的四份交付物：三个算法 / 评审任务（A、B、C）和一个可运行的
全栈商品详情页（`app/`）。所有命令都在 **仓库根目录** 下执行，Windows 用
PowerShell，macOS / Linux 的差异已单独标注。

| 目录 | 内容 | 一句话说明 |
| --- | --- | --- |
| [`A/`](A/) | `task_a.py` + `test_task_a.py` | 库存预留账本：确定性状态机 + 幂等 |
| [`B/`](B/) | `task_b.py` + `test_task_b.py` | 履约拆仓优化：DP + 多级并列规则 |
| [`C/`](C/) | [`answers.md`](C/answers.md) | Xero 多租户集成评审（C1–C6） |
| [`app/backend/`](app/backend/) | FastAPI 后端 | 商品详情 / 购物车，服务端定价与幂等 |
| [`app/frontend/`](app/frontend/) | React + TS + Vite 前端 | 变体 PDP，含错误态与陈旧库存自愈 |

---

## 1. 环境要求

| 依赖 | 版本 | 实测版本 |
| --- | --- | --- |
| Python | 3.11+ | 3.13.2 |
| Node.js | 18+ | 26.13.0 |
| npm | 随 Node 附带 | 11.x |

Windows 上如果 PowerShell 禁止执行脚本（`npm.ps1 无法加载`），把命令里的
`npm` 换成 `npm.cmd` 即可，本 README 与启动脚本都已经这样处理。

---

## 2. 一键启动（推荐）

```powershell
.\dev.bat            # 或：powershell -ExecutionPolicy Bypass -File .\dev.ps1
```

脚本会自动完成：检查 Python / Node → 创建后端 `.venv` 并安装依赖 →
安装前端依赖并准备 `.env` → 启动 FastAPI（`127.0.0.1:8000`）→
等后端健康检查通过后再启动 Vite（`127.0.0.1:5173`）。
按 `Ctrl+C` 会同时结束两个进程。

> 如果直接运行 `.\dev.ps1` 报「在此系统上禁止运行脚本」，是本机 PowerShell
> 执行策略较严。用 `.\dev.bat` 即可（它内部以 `-ExecutionPolicy Bypass` 调用），
> 或手动执行 `powershell -ExecutionPolicy Bypass -File .\dev.ps1`。

只想跑测试、不想起服务时，直接用第 4 节的命令。

---

## 3. 分步启动

### 3.1 后端（FastAPI，默认 8000）

```powershell
cd app\backend
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn main:app --reload
```

macOS / Linux 把 `.venv\Scripts\python.exe` 换成 `.venv/bin/python`。

国内网络如果 `pip install` 长时间没反应，是 PyPI 直连被中断，换成清华镜像重跑即可（实测 10 秒装完）：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

启动后：

- Swagger UI：<http://127.0.0.1:8000/docs>
- 商品详情：<http://127.0.0.1:8000/api/products/tee-001>
- 购物车：<http://127.0.0.1:8000/api/cart>

> 不想建 venv 也可以，直接 `py -m pip install -r requirements.txt` 后
> `py -m uvicorn main:app --reload`；下面的测试命令同理。

### 3.2 前端（Vite，默认 5173）

```powershell
cd app\frontend
npm install     # 或 npm ci（仓库已提交 package-lock.json，可完全复现）
npm run dev
```

`vite.config.ts` 默认把 `/api` 代理到 `http://127.0.0.1:8000`，所以**不复制
`.env` 也能直接跑**。要指向别的后端时再复制配置：

```powershell
copy .env.example .env    # macOS / Linux: cp .env.example .env
```

Windows 也可以直接双击 `app\frontend\start-pdp.bat`。

---

## 4. 测试（全部可直接复制运行）

| 目标 | 命令（仓库根目录） | 期望输出 |
| --- | --- | --- |
| Task A | `cd A` → `py -m pytest -q test_task_a.py` | `34 passed` |
| Task B | `cd B` → `py test_task_b.py` | `all ok`（约 30 秒，含 1000 组随机对拍） |
| 后端 | `cd app\backend` → `py -m pytest -q test_main.py` | `11 passed` |
| 前端测试 | `cd app\frontend` → `npm test` | `Tests  7 passed (7)` |
| 前端类型 | `cd app\frontend` → `npm run typecheck` | 无输出即通过 |
| 前端构建 | `cd app\frontend` → `npm run build` | `✓ built in ...` |

Task B 的测试是**独立脚本**（不依赖 pytest），会先用 7 条固定用例覆盖
无解 / 零库存仓库 / 成本并列 / 编号按字符串比较 / 大数量 / W=30 并列，
再跑 1000 组随机数据与暴力法逐项比对；全部通过才打印 `all ok`。

### 已验证记录（2026-11-03）

| 命令 | 结果 |
| --- | --- |
| `py -m pytest -q test_task_a.py` | 34 passed，1.3s |
| `py test_task_b.py` | all ok，30.7s |
| `py -m pytest -q test_main.py` | 11 passed，0.3s |
| `npm test` | 7 passed，2.4s |
| `npm run build` | 成功，44 modules，dist 约 159 kB JS |
| 后端样例输入 `10 6 / RESERVE ...` | 输出与题目样例逐行一致 |

---

## 5. 文件导览：哪段代码实现了什么

| 要求 | 位置 |
| --- | --- |
| A：确定性库存处理器、幂等、非法输入不改变状态 | [`A/task_a.py`](A/task_a.py) |
| A：边界与重放测试、复杂度说明 | [`A/test_task_a.py`](A/test_task_a.py)、脚本头注释 |
| B：最少仓库 → 最低成本 → 字典序最小 | [`B/task_b.py`](B/task_b.py) |
| B：状态表示 / 并列策略 / 复杂度说明 | `task_b.py` 模块 docstring |
| B：无解 / 零库存 / 并列 / 大数量测试 | `B/test_task_b.py` 的 `run_fixed_cases()` |
| C：C1–C6 + 假设 + 官方文档引用 | [`C/answers.md`](C/answers.md) |
| 后端：服务端定价、幂等、防超卖、结构化错误 | [`app/backend/main.py`](app/backend/main.py) |
| 后端：成功 / 校验 / 幂等 / 竞态测试 | [`app/backend/test_main.py`](app/backend/test_main.py) |
| 前端：变体解析、禁用不可用组合、错误态 | [`app/frontend/src/`](app/frontend/src/) |
| 前端：≥3 个有意义的测试 | [`app/frontend/src/App.test.tsx`](app/frontend/src/App.test.tsx) |
| 前端：375px / 1280px 截图 | [`app/frontend/docs/`](app/frontend/docs/) |

---

## 6. API 契约

所有错误响应统一为 `{"error_code": "...", "message": "..."}`。
价格单位元，服务端返回两位小数。

### `GET /api/products/{product_id}`

| 状态码 | `error_code` | 含义 |
| --- | --- | --- |
| 200 | — | 成功，返回商品与全部 SKU |
| 404 | `PRODUCT_NOT_FOUND` | 商品 ID 不存在 |

```json
{
  "id": "tee-001",
  "name": "云感纯棉圆领 T 恤",
  "description": "260g 精梳棉，宽松版型，日常百搭。",
  "currency": "CNY",
  "options": [
    { "key": "color", "name": "颜色", "values": [{ "value": "red", "label": "红色" }] },
    { "key": "size", "name": "尺寸", "values": [{ "value": "XL", "label": "XL" }] }
  ],
  "skus": [
    {
      "id": "SKU-RED-M",
      "color": "red",
      "color_label": "红色",
      "size": "M",
      "price": 99.0,
      "stock": 3,
      "available": true,
      "image": "/images/tee-red.svg"
    }
  ]
}
```

种子数据：2 色 × 4 码 = 8 种组合，其中 **「蓝色 XL」没有 SKU**（不可用组合），
**「红色 S」库存为 0**（缺货 SKU），共 7 个 SKU。

### `POST /api/cart/items`

请求头必须带 `Idempotency-Key`；请求体只接受 `sku_id` 与 `quantity`
（多传 `price` 会得到 422，因为模型设置了 `extra="forbid"`）。

```http
POST /api/cart/items
Content-Type: application/json
Idempotency-Key: 1f8a6f90-23d5-4f36-9c2c-6f3c6a40b2ef

{ "sku_id": "SKU-RED-M", "quantity": 2 }
```

| 状态码 | `error_code` | 含义 |
| --- | --- | --- |
| 200 | — | 加购成功，返回**加购后的完整购物车** |
| 400 | `MISSING_IDEMPOTENCY_KEY` | 缺少或为空的 `Idempotency-Key` |
| 400 | `INVALID_IDEMPOTENCY_KEY` | Key 超过 255 字符 |
| 400 | `INSUFFICIENT_STOCK` | 请求数量超过服务端当前库存（含库存 0） |
| 404 | `SKU_NOT_FOUND` | SKU 不存在 |
| 409 | `IDEMPOTENCY_KEY_REUSED` | 同一 Key 复用于不同参数 |
| 422 | `VALIDATION_ERROR` | 请求体结构不合法（缺字段、数量 ≤ 0、多传字段） |

同一个 Key + 同样参数重复提交，返回第一次的响应（状态码也一样），
不会重复扣库存或重复加购。

### `GET /api/cart`

| 状态码 | 含义 |
| --- | --- |
| 200 | 当前购物车快照 |

```json
{
  "items": [
    {
      "sku_id": "SKU-RED-M",
      "product_id": "tee-001",
      "color": "red",
      "color_label": "红色",
      "size": "M",
      "unit_price": 99.0,
      "quantity": 2,
      "line_total": 198.0
    }
  ],
  "total_items": 2,
  "total_amount": 198.0
}
```

其他通用状态码：未知路径 `404 NOT_FOUND`，方法不允许 `405 METHOD_NOT_ALLOWED`，
未捕获异常 `500 INTERNAL_ERROR`。

---

## 7. 设计说明

只记几个不显然的决定，推导过程见代码注释。

### Task A：event_id 在参数校验之前就消费

无论成功、业务拒绝还是格式错误，同一个 event_id 第二次出现一律 `DUPLICATE`。
这是题目“被拒绝的业务操作也算处理过”的直接结果；代价是一个写错的 event_id
会被永久占用，后续同 id 的合法指令只能拿到 DUPLICATE。

### Task B：掩码怎么代表字典序

仓库按 id 升序处理，编号越小占的二进制位越高。等长集合比较时第一个不同的
编号决定字典序，所以成本相同时保留掩码更大的集合即可（`task_b.py:146`）。
转移里对“当前仓库分几件”的枚举用单调队列做到 O(1)，整体 O(W²·Q)。

### App：两个不显然的点

- 库存校验、扣减、写购物车、写幂等记录在同一把 `asyncio.Lock` 内完成，
  少锁任何一步都会超卖。
- 选择状态拆成四种（未选完 / 组合不存在 / 组合缺货 / 可购买），
  因为“缺货”和“没这个组合”要给用户不同的提示。

---

## 8. 假设

- 评测环境以 Windows + PowerShell 为主，macOS / Linux 的差异已在命令旁标注。
- Task B 的“字典序最小”按 `warehouse_id` 的字符串比较（`"10" < "2"`），与题目示例一致；
  `Q = 0` 视为无需选仓、成本 0，输出 `0 0`。
- Task A 的输入行数不少于 N；若实际不足，按已有指令处理完毕。
- Task C 假设 Xero Accounting API 2.0、OAuth 2.0 授权码 + PKCE、机密客户端，
  具体数值以官方文档为准。

---

## 9. 已知限制

- 单进程、内存存储：重启后购物车、库存、幂等记录全部重置，多 worker 之间也不共享锁。
  生产环境要换数据库或 Redis，并用分布式锁或原子更新。
- 没有用户体系，只有一个全局购物车；也没配 CORS，前端依赖 Vite 同源代理。
- 幂等记录不过期，`_idempotency` 只增不减。
- Task B 按题目规模（W ≤ 30、Q ≤ 2000）设计，规模再大需要换算法。
- 前端测试是组件级的，没有真实浏览器 E2E；布局以 `docs/` 的截图为准。
- 按题目要求，支付、结算、部署都不做。

---

## 10. AI 使用披露

本题允许使用 AI 工具，但要求披露范围。以下是我实际的使用方式：

- 本题的代码由 AI 辅助生成；我负责需求拆解、代码阅读、测试运行与结论确认。
- 仓库中的每个测试用例和设计决定，都能对应到代码注释或本文档的相应小节。
- 未使用任何真实客户数据、密钥或第三方账号；种子数据全部是虚构数据。

---

## 11. 常见问题与排查

| 现象 | 处理 |
| --- | --- |
| `.\dev.ps1` 报「禁止运行脚本」 | 改用 `.\dev.bat`，或 `powershell -ExecutionPolicy Bypass -File .\dev.ps1` |
| `npm` 报「npm.ps1 无法加载」 | 命令里用 `npm.cmd` 代替 `npm` |
| `pip install` 很慢 / 超时 | 换国内镜像：`py -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| `npm install` 很慢 | `npm config set registry https://registry.npmmirror.com` |
| 端口被占用 | `.\dev.bat -BackendPort 8010 -FrontendPort 5180`（脚本会把端口同步给 Vite 代理） |
| 前端页面空白 / 请求 404 | 先确认后端已启动；开发时 `/api` 由 Vite 代理到 `127.0.0.1:8000` |
| 商品页一直加载失败 | 打开浏览器控制台看 `/api/products/tee-001` 的返回，或直接访问 <http://127.0.0.1:8000/api/products/tee-001> |
| 测试通过但页面库存不对 | 后端是内存存储，重启后库存会重置回种子数据 |
