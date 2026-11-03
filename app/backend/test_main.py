"""main.py 的 pytest 测试。

Starlette 的 TestClient 本身就是 httpx.Client 的子类，并共享同一个事件循环，
所以这里的并发用例既走真实 ASGI 请求，也能让应用内的 asyncio.Lock 真正生效。

运行：
    pytest -q test_main.py
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app

PRODUCT_URL = "/api/products/tee-001"
CART_URL = "/api/cart"
CART_ITEMS_URL = "/api/cart/items"


@pytest.fixture()
def client():
    # 每次进入 with 都会触发 lifespan：重置种子数据并创建属于当前事件循环的锁。
    with TestClient(app) as test_client:
        assert isinstance(test_client, httpx.Client)
        yield test_client


def _add(client: TestClient, *, sku_id: str, quantity: int, key: str) -> httpx.Response:
    return client.post(
        CART_ITEMS_URL,
        json={"sku_id": sku_id, "quantity": quantity},
        headers={"Idempotency-Key": key},
    )


def _sku_map(client: TestClient) -> dict[str, dict]:
    response = client.get(PRODUCT_URL)
    assert response.status_code == 200
    return {sku["id"]: sku for sku in response.json()["skus"]}


# ---------------------------------------------------------------------------
# 1. 商品详情
# ---------------------------------------------------------------------------


def test_get_product_success(client: TestClient) -> None:
    response = client.get(PRODUCT_URL)

    assert response.status_code == 200
    product = response.json()
    assert product["id"] == "tee-001"
    assert product["name"] == "云感纯棉圆领 T 恤"
    assert product["currency"] == "CNY"

    dimensions = {option["key"]: option for option in product["options"]}
    assert set(dimensions) == {"color", "size"}
    assert [value["value"] for value in dimensions["color"]["values"]] == [
        "red",
        "blue",
    ]
    assert [value["value"] for value in dimensions["size"]["values"]] == [
        "S",
        "M",
        "L",
        "XL",
    ]

    skus = product["skus"]
    assert len(skus) == 7
    combos = {(sku["color"], sku["size"]) for sku in skus}
    assert combos == {
        ("red", "S"),
        ("red", "M"),
        ("red", "L"),
        ("red", "XL"),
        ("blue", "S"),
        ("blue", "M"),
        ("blue", "L"),
    }
    # 「蓝色 XL」是刻意的不可用组合：维度里有 XL，但没有这个组合的 SKU。
    assert ("blue", "XL") not in combos
    # 每个 SKU 都必须带自己的图片。
    assert all(sku["image"].startswith("/images/") for sku in skus)
    sku_by_id = {sku["id"]: sku for sku in skus}
    assert sku_by_id["SKU-RED-S"]["stock"] == 0
    assert sku_by_id["SKU-RED-S"]["available"] is False
    assert sku_by_id["SKU-BLUE-L"]["stock"] == 1
    assert all(
        sku["available"] is (sku["stock"] > 0)
        for sku in skus
    )


def test_impossible_combination_has_no_sku(client: TestClient) -> None:
    """不可用组合：维度提供 XL，但「蓝色 + XL」没有 SKU，前端据此禁用按钮。"""
    product = client.get(PRODUCT_URL).json()
    size_option = next(o for o in product["options"] if o["key"] == "size")
    assert "XL" in [value["value"] for value in size_option["values"]]

    combos = {(sku["color"], sku["size"]) for sku in product["skus"]}
    assert ("blue", "XL") not in combos
    assert ("red", "XL") in combos


def test_sku_images_are_served_by_the_api(client: TestClient) -> None:
    """图片属于 SKU 自己的字段，不是前端按颜色猜的。"""
    skus = client.get(PRODUCT_URL).json()["skus"]
    red = next(sku for sku in skus if sku["id"] == "SKU-RED-M")
    blue = next(sku for sku in skus if sku["id"] == "SKU-BLUE-M")
    assert red["image"] == "/images/tee-red.svg"
    assert blue["image"] == "/images/tee-blue.svg"


# ---------------------------------------------------------------------------
# 2. 成功加购：价格由后端决定
# ---------------------------------------------------------------------------


def test_add_to_cart_success_uses_server_price(client: TestClient) -> None:
    response = _add(client, sku_id="SKU-RED-M", quantity=2, key="cart-success-1")

    assert response.status_code == 200
    cart = response.json()
    assert cart["total_items"] == 2
    assert cart["total_amount"] == 198.0  # 服务端单价 99.00 * 2
    assert len(cart["items"]) == 1
    assert cart["items"][0] == {
        "sku_id": "SKU-RED-M",
        "product_id": "tee-001",
        "color": "red",
        "color_label": "红色",
        "size": "M",
        "unit_price": 99.0,
        "quantity": 2,
        "line_total": 198.0,
    }

    # GET /api/cart 与加购结果一致。
    current = client.get(CART_URL)
    assert current.status_code == 200
    assert current.json() == cart

    # 服务端库存确实只扣减了一次请求的数量。
    assert _sku_map(client)["SKU-RED-M"]["stock"] == 1


def test_client_supplied_price_is_rejected(client: TestClient) -> None:
    """客户端多传 price 不会被静默信任，而是返回结构化参数错误。"""
    response = client.post(
        CART_ITEMS_URL,
        json={"sku_id": "SKU-RED-M", "quantity": 1, "price": 0.01},
        headers={"Idempotency-Key": "malicious-price"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert "message" in response.json()
    assert client.get(CART_URL).json()["total_items"] == 0


# ---------------------------------------------------------------------------
# 3. 幂等性：同一个 Key 只加购一次
# ---------------------------------------------------------------------------


def test_idempotency_same_key_adds_only_once(client: TestClient) -> None:
    first = _add(client, sku_id="SKU-BLUE-S", quantity=2, key="same-key-abc")
    second = _add(client, sku_id="SKU-BLUE-S", quantity=2, key="same-key-abc")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    cart = client.get(CART_URL).json()
    assert cart["total_items"] == 2
    assert cart["items"][0]["quantity"] == 2

    # 初始库存 4，两次相同请求也只能扣 2。
    assert _sku_map(client)["SKU-BLUE-S"]["stock"] == 2


def test_idempotency_key_cannot_be_reused_with_different_payload(
    client: TestClient,
) -> None:
    first = _add(client, sku_id="SKU-RED-L", quantity=1, key="conflict-key")
    assert first.status_code == 200

    conflict = _add(client, sku_id="SKU-RED-L", quantity=2, key="conflict-key")
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"

    # 冲突请求不会产生额外扣减或加购。
    assert client.get(CART_URL).json()["total_items"] == 1
    assert _sku_map(client)["SKU-RED-L"]["stock"] == 4


# ---------------------------------------------------------------------------
# 4. 库存不足
# ---------------------------------------------------------------------------


def test_insufficient_stock_returns_structured_400(client: TestClient) -> None:
    response = _add(
        client,
        sku_id="SKU-RED-M",
        quantity=4,  # 只剩 3 件
        key="insufficient-key",
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "INSUFFICIENT_STOCK"
    assert "库存不足" in body["message"]

    # 失败请求不能改变库存或购物车。
    assert client.get(CART_URL).json()["total_items"] == 0
    assert _sku_map(client)["SKU-RED-M"]["stock"] == 3


def test_out_of_stock_sku_cannot_be_added(client: TestClient) -> None:
    response = _add(client, sku_id="SKU-RED-S", quantity=1, key="oos-key")

    assert response.status_code == 400
    assert response.json()["error_code"] == "INSUFFICIENT_STOCK"
    assert client.get(CART_URL).json()["total_items"] == 0


def test_missing_idempotency_key_is_structured(client: TestClient) -> None:
    response = client.post(
        CART_ITEMS_URL, json={"sku_id": "SKU-RED-M", "quantity": 1}
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "MISSING_IDEMPOTENCY_KEY"
    assert "message" in response.json()


# ---------------------------------------------------------------------------
# 5. 并发抢最后一件：多线程同时请求，只能有一个成功
# ---------------------------------------------------------------------------


def test_concurrent_purchase_of_last_item(client: TestClient) -> None:
    barrier = threading.Barrier(2)

    def buy(key: str) -> httpx.Response:
        barrier.wait(timeout=5)
        return _add(client, sku_id="SKU-BLUE-L", quantity=1, key=key)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(buy, f"race-{index}") for index in range(2)]
        responses = [future.result(timeout=10) for future in futures]

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 400], [
        (response.status_code, response.json()) for response in responses
    ]

    failure = next(response for response in responses if response.status_code == 400)
    assert failure.json()["error_code"] == "INSUFFICIENT_STOCK"

    cart = client.get(CART_URL).json()
    assert cart["total_items"] == 1
    assert len(cart["items"]) == 1
    assert cart["items"][0]["sku_id"] == "SKU-BLUE-L"
    assert cart["items"][0]["quantity"] == 1

    assert _sku_map(client)["SKU-BLUE-L"]["stock"] == 0
