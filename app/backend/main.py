"""电商商品详情页 / 购物车后端（FastAPI + 内存存储）。

价格与库存只以服务端为准，客户端只能提交 sku_id 和 quantity；加购的
“查库存 → 扣减 → 写购物车 → 记幂等”在同一个 asyncio.Lock 内完成。
错误统一返回 {"error_code": "...", "message": "..."}。

运行：uvicorn main:app --reload
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

PRODUCT_ID = "tee-001"
CURRENCY = "CNY"


# ---------------------------------------------------------------------------
# 服务端种子数据（客户端永远不能覆盖这些价格和库存）
# ---------------------------------------------------------------------------


@dataclass
class SkuRecord:
    id: str
    product_id: str
    color: Literal["red", "blue"]
    color_label: str
    size: Literal["S", "M", "L", "XL"]
    price_cents: int
    stock: int
    image: str


@dataclass(frozen=True)
class ProductRecord:
    id: str
    name: str
    description: str
    currency: str


PRODUCT = ProductRecord(
    id=PRODUCT_ID,
    name="云感纯棉圆领 T 恤",
    description="260g 精梳棉，宽松版型，日常百搭。",
    currency=CURRENCY,
)

# 2 个维度 x 4 个值 = 8 种组合，其中「蓝色 XL」故意不提供 SKU：
# 这样既满足「至少 6 个 SKU」，又能演示两类不同的问题状态——
#   * 不可用组合：维度里存在 XL，但「蓝色 + XL」没有对应 SKU；
#   * 缺货 SKU：红-S 库存为 0。
# 蓝-L 只剩 1 件，用于并发抢最后一件的测试。
# 每个 SKU 都带自己的 image，前端直接渲染，不再依赖颜色硬编码。
SEED_SKUS: tuple[SkuRecord, ...] = (
    SkuRecord("SKU-RED-S", PRODUCT_ID, "red", "红色", "S", 8900, 0, "/images/tee-red.svg"),
    SkuRecord("SKU-RED-M", PRODUCT_ID, "red", "红色", "M", 9900, 3, "/images/tee-red.svg"),
    SkuRecord("SKU-RED-L", PRODUCT_ID, "red", "红色", "L", 10900, 5, "/images/tee-red.svg"),
    SkuRecord("SKU-RED-XL", PRODUCT_ID, "red", "红色", "XL", 11900, 2, "/images/tee-red.svg"),
    SkuRecord("SKU-BLUE-S", PRODUCT_ID, "blue", "蓝色", "S", 9900, 4, "/images/tee-blue.svg"),
    SkuRecord("SKU-BLUE-M", PRODUCT_ID, "blue", "蓝色", "M", 10900, 2, "/images/tee-blue.svg"),
    SkuRecord("SKU-BLUE-L", PRODUCT_ID, "blue", "蓝色", "L", 11900, 1, "/images/tee-blue.svg"),
)

_skus: dict[str, SkuRecord] = {}
_cart: dict[str, int] = {}  # sku_id -> quantity（单购物车示例）
_idempotency: dict[str, "IdempotencyRecord"] = {}


@dataclass(frozen=True)
class IdempotencyRecord:
    fingerprint: str
    status_code: int
    body: dict[str, Any]


def reset_state() -> None:
    """重置内存状态。应用启动时调用；测试也可直接调用来隔离用例。"""
    global _skus
    _skus = {
        seed.id: SkuRecord(
            id=seed.id,
            product_id=seed.product_id,
            color=seed.color,
            color_label=seed.color_label,
            size=seed.size,
            price_cents=seed.price_cents,
            stock=seed.stock,
            image=seed.image,
        )
        for seed in SEED_SKUS
    }
    _cart.clear()
    _idempotency.clear()


reset_state()  # 导入时就有可用的种子数据（即使不经过 lifespan）


# ---------------------------------------------------------------------------
# 响应 / 请求模型
# ---------------------------------------------------------------------------


class OptionValue(BaseModel):
    value: str
    label: str


class OptionDimension(BaseModel):
    key: str
    name: str
    values: list[OptionValue]


class SkuOut(BaseModel):
    id: str
    color: str
    color_label: str
    size: str
    price: float
    stock: int
    available: bool
    image: str


class ProductOut(BaseModel):
    id: str
    name: str
    description: str
    currency: str
    options: list[OptionDimension]
    skus: list[SkuOut]


class AddCartItemRequest(BaseModel):
    # extra="forbid"：客户端传 price 等字段会直接得到结构化校验错误，避免误解为可改价。
    model_config = ConfigDict(extra="forbid")

    sku_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(gt=0)


class CartItemOut(BaseModel):
    sku_id: str
    product_id: str
    color: str
    color_label: str
    size: str
    unit_price: float
    quantity: int
    line_total: float


class CartOut(BaseModel):
    items: list[CartItemOut]
    total_items: int
    total_amount: float


class ErrorOut(BaseModel):
    error_code: str
    message: str


# ---------------------------------------------------------------------------
# 统一错误
# ---------------------------------------------------------------------------


class ApiError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message

    def as_body(self) -> dict[str, str]:
        return {"error_code": self.error_code, "message": self.message}


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error_code": error_code, "message": message},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 每次应用启动都重建内存数据和与当前事件循环绑定的锁。
    reset_state()
    app.state.cart_lock = asyncio.Lock()
    yield


app = FastAPI(
    title="商品详情与购物车 API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return _error_response(exc.status_code, exc.error_code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    reason = str(first.get("msg", "请求参数不合法"))
    message = f"请求参数校验失败：{location} {reason}".strip()
    return _error_response(422, "VALIDATION_ERROR", message)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(
    _: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if isinstance(exc.detail, dict):
        error_code = str(exc.detail.get("error_code", "HTTP_ERROR"))
        message = str(exc.detail.get("message", "请求失败"))
    else:
        error_code = {
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
        }.get(exc.status_code, "HTTP_ERROR")
        message = str(exc.detail)
    return _error_response(exc.status_code, error_code, message)


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error", exc_info=exc)
    return _error_response(500, "INTERNAL_ERROR", "服务器内部错误，请稍后重试。")


# ---------------------------------------------------------------------------
# 序列化与购物车构造
# ---------------------------------------------------------------------------


def _price(cents: int) -> float:
    return round(cents / 100, 2)


def _product_options() -> list[OptionDimension]:
    return [
        OptionDimension(
            key="color",
            name="颜色",
            values=[
                OptionValue(value="red", label="红色"),
                OptionValue(value="blue", label="蓝色"),
            ],
        ),
        OptionDimension(
            key="size",
            name="尺寸",
            values=[
                OptionValue(value="S", label="S"),
                OptionValue(value="M", label="M"),
                OptionValue(value="L", label="L"),
                OptionValue(value="XL", label="XL"),
            ],
        ),
    ]


def _sku_out(sku: SkuRecord) -> SkuOut:
    return SkuOut(
        id=sku.id,
        color=sku.color,
        color_label=sku.color_label,
        size=sku.size,
        price=_price(sku.price_cents),
        stock=sku.stock,
        available=sku.stock > 0,
        image=sku.image,
    )


def _build_cart() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    total_items = 0
    total_cents = 0

    for sku_id, quantity in _cart.items():
        sku = _skus[sku_id]
        line_cents = sku.price_cents * quantity
        total_items += quantity
        total_cents += line_cents
        items.append(
            {
                "sku_id": sku.id,
                "product_id": sku.product_id,
                "color": sku.color,
                "color_label": sku.color_label,
                "size": sku.size,
                "unit_price": _price(sku.price_cents),
                "quantity": quantity,
                "line_total": _price(line_cents),
            }
        )

    return {
        "items": items,
        "total_items": total_items,
        "total_amount": _price(total_cents),
    }


def _get_cart_lock(request: Request) -> asyncio.Lock:
    """优先使用 lifespan 创建的锁；未运行 lifespan 时惰性创建。"""
    lock = getattr(request.app.state, "cart_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        request.app.state.cart_lock = lock
    return lock


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------


@app.get(
    "/api/products/{product_id}",
    response_model=ProductOut,
    responses={404: {"model": ErrorOut}},
)
async def get_product(product_id: str) -> ProductOut:
    if product_id != PRODUCT.id:
        raise ApiError(404, "PRODUCT_NOT_FOUND", f"商品 {product_id} 不存在。")

    return ProductOut(
        id=PRODUCT.id,
        name=PRODUCT.name,
        description=PRODUCT.description,
        currency=PRODUCT.currency,
        options=_product_options(),
        skus=[_sku_out(_skus[seed.id]) for seed in SEED_SKUS],
    )


@app.post(
    "/api/cart/items",
    response_model=CartOut,
    responses={
        400: {"model": ErrorOut},
        404: {"model": ErrorOut},
        409: {"model": ErrorOut},
        422: {"model": ErrorOut},
    },
)
async def add_cart_item(
    payload: AddCartItemRequest,
    request: Request,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key")
    ] = None,
):
    key = (idempotency_key or "").strip()
    if not key:
        raise ApiError(
            400,
            "MISSING_IDEMPOTENCY_KEY",
            "请求头必须携带非空的 Idempotency-Key。",
        )
    if len(key) > 255:
        raise ApiError(
            400,
            "INVALID_IDEMPOTENCY_KEY",
            "Idempotency-Key 长度不能超过 255 个字符。",
        )

    # 同一 Key 只能对应同一份请求参数；否则说明客户端复用了 Key。
    fingerprint = f"{payload.sku_id}\x00{payload.quantity}"
    lock = _get_cart_lock(request)

    async with lock:
        cached = _idempotency.get(key)
        if cached is not None:
            if cached.fingerprint != fingerprint:
                raise ApiError(
                    409,
                    "IDEMPOTENCY_KEY_REUSED",
                    "该 Idempotency-Key 已用于不同的请求参数。",
                )
            # 返回第一次请求的完全相同的结果，不重复加购 / 扣库存。
            return JSONResponse(status_code=cached.status_code, content=cached.body)

        sku = _skus.get(payload.sku_id)
        if sku is None:
            result_status = 404
            result_body = {
                "error_code": "SKU_NOT_FOUND",
                "message": f"SKU {payload.sku_id} 不存在。",
            }
        elif payload.quantity > sku.stock:
            result_status = 400
            result_body = {
                "error_code": "INSUFFICIENT_STOCK",
                "message": (
                    f"库存不足：SKU {sku.id} 仅剩 {sku.stock} 件，"
                    f"请求 {payload.quantity} 件。"
                ),
            }
        else:
            # 所有检查通过后才在锁内扣减库存并写购物车。
            sku.stock -= payload.quantity
            _cart[sku.id] = _cart.get(sku.id, 0) + payload.quantity
            result_status = 200
            result_body = _build_cart()

        # 缓存成功和业务失败两种结果，保证同一 Key 重放时结果稳定。
        _idempotency[key] = IdempotencyRecord(
            fingerprint=fingerprint,
            status_code=result_status,
            body=result_body,
        )

    return JSONResponse(status_code=result_status, content=result_body)


@app.get("/api/cart", response_model=CartOut)
async def get_cart(request: Request) -> CartOut:
    # 与加购使用同一把锁，保证读取到的是一个完成后的购物车快照。
    async with _get_cart_lock(request):
        return CartOut.model_validate(_build_cart())
