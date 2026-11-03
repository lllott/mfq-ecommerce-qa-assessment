# 电商商品详情 / 购物车后端

基于 Python 3.11+、FastAPI、Pydantic 2 的内存版后端示例。

## 运行

在 `backend` 目录（本 README 所在目录）下执行：

```bash
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn main:app --reload
```

启动后：

- 接口文档：<http://127.0.0.1:8000/docs>
- 商品详情：<http://127.0.0.1:8000/api/products/tee-001>
- 购物车：<http://127.0.0.1:8000/api/cart>

## 测试

在 `backend` 目录下执行：

```bash
py -m pytest -q test_main.py
```

覆盖场景：商品详情、不可用组合、SKU 图片、成功加购、服务端价格保护、幂等重放、幂等 Key 冲突、库存不足、缺货 SKU、缺失 Idempotency-Key、多线程抢最后一件。

## API

### GET /api/products/{product_id}

返回商品、颜色/尺寸两个维度以及 7 个 SKU：2 色 × 4 码共 8 种组合，其中「蓝色 XL」刻意不提供 SKU（演示不可用组合），「红色 S」库存为 0（演示缺货）。每个 SKU 都带自己的 `image` 字段。

### POST /api/cart/items

请求头必须包含 `Idempotency-Key`：

```http
Content-Type: application/json
Idempotency-Key: demo-001
```

请求体：

```json
{
  "sku_id": "SKU-RED-M",
  "quantity": 2
}
```

价格和库存全部以服务端数据为准。相同 Key 重放返回第一次的相同结果，不会重复加购；相同 Key 搭配不同参数返回 409。

### GET /api/cart

返回购物车条目、总件数 `total_items` 和总金额 `total_amount`。

## 错误格式

```json
{
  "error_code": "INSUFFICIENT_STOCK",
  "message": "库存不足：SKU SKU-RED-M 仅剩 3 件，请求 4 件。"
}
```

## 实现说明

- 库存检查和扣减、购物车写入、幂等记录写入都由同一个 `asyncio.Lock()` 保护，避免并发超卖。
- 客户端不能提交价格；请求模型设置了 `extra="forbid"`，额外传 `price` 会得到 422。
- 幂等结果保存在内存字典中，成功和业务失败结果都会被缓存。

## 已知边界

这是单进程内存示例：应用重启后购物车、库存和幂等记录都会重置；多个 worker 或多个实例之间不共享锁和数据。生产环境应改用数据库/Redis，并使用分布式锁或原子更新。当前也没有用户登录、购物车隔离和 CORS 配置；如需从其他端口的前端页面直接调用，需要另外添加 CORS 中间件。
