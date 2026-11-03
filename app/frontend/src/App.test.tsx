import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, type Mock } from "vitest";
import App from "./App";
import { cartResponseFixture, productResponseFixture } from "./test/fixtures";

type FetchMock = Mock<typeof fetch>;

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
}

interface MockOptions {
  productResponses?: Response[];
  postResponse?: Promise<Response>;
}

function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function installFetchMock(options: MockOptions = {}): FetchMock {
  const fetchMock = vi.fn<typeof fetch>();
  const productResponses = [...(options.productResponses ?? [])];

  fetchMock.mockImplementation(async (input, init) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    const method = init?.method ?? "GET";

    if (url.endsWith("/api/products/tee-001") && method === "GET") {
      const nextResponse = productResponses.shift();
      return nextResponse ?? jsonResponse(productResponseFixture);
    }

    if (url.endsWith("/api/cart") && method === "GET") {
      return jsonResponse(cartResponseFixture);
    }

    if (url.endsWith("/api/cart/items") && method === "POST") {
      return (
        options.postResponse ?? Promise.resolve(new Response(null, { status: 201 }))
      );
    }

    return new Response("Not Found", { status: 404 });
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function getPostCalls(fetchMock: FetchMock): [RequestInfo | URL, RequestInit?][] {
  return fetchMock.mock.calls.filter(
    ([, init]) => (init?.method ?? "GET") === "POST",
  );
}

function getProductGetCalls(fetchMock: FetchMock): [RequestInfo | URL, RequestInit?][] {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      (init?.method ?? "GET") === "GET" &&
      String(url).includes("/api/products/"),
  );
}

async function renderLoadedApp(): Promise<void> {
  render(<App />);
  await screen.findByRole("heading", { name: productResponseFixture.name });
}

describe("Variant PDP", () => {
  it("颜色 / 尺寸切换后，价格、库存和图片都精确跟随 SKU 更新", async () => {
    const user = userEvent.setup();
    installFetchMock();
    await renderLoadedApp();

    expect(screen.getByTestId("product-price")).toHaveTextContent("¥89.00 起");

    await user.click(screen.getByRole("button", { name: "颜色 蓝色" }));
    await user.click(screen.getByRole("button", { name: "尺寸 M" }));

    expect(screen.getByTestId("product-price")).toHaveTextContent("¥109.00");
    expect(screen.getByTestId("stock-status")).toHaveTextContent("库存 2 件");
    expect(
      screen.getByRole("img", { name: "云感纯棉圆领 T 恤，蓝色，M" }),
    ).toHaveAttribute("src", "/images/tee-blue.svg");

    await user.click(screen.getByRole("button", { name: "颜色 红色" }));
    expect(screen.getByTestId("product-price")).toHaveTextContent("¥99.00");
    expect(screen.getByTestId("stock-status")).toHaveTextContent("库存 3 件");
    expect(
      screen.getByRole("img", { name: "云感纯棉圆领 T 恤，红色，M" }),
    ).toHaveAttribute("src", "/images/tee-red.svg");

    await user.click(screen.getByRole("button", { name: "尺寸 L" }));
    expect(screen.getByTestId("stock-status")).toHaveTextContent("库存 5 件");
  });

  it("选到缺货组合时，缺货尺寸与加购按钮都被禁用", async () => {
    const user = userEvent.setup();
    installFetchMock();
    await renderLoadedApp();

    const addButton = screen.getByRole("button", { name: "加入购物车" });
    expect(addButton).toBeDisabled();

    // 先选全局有货的 S，再切到该尺寸缺货的红色。
    await user.click(screen.getByRole("button", { name: "尺寸 S" }));
    await user.click(screen.getByRole("button", { name: "颜色 红色" }));

    expect(screen.getByTestId("stock-status")).toHaveTextContent(
      "该组合暂时缺货",
    );
    expect(
      screen.getByRole("button", { name: "尺寸 S，缺货" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "加入购物车" })).toBeDisabled();
  });

  it("选到根本不存在的组合（蓝色 + XL）时提示不可选，而不是缺货", async () => {
    const user = userEvent.setup();
    installFetchMock();
    await renderLoadedApp();

    await user.click(screen.getByRole("button", { name: "尺寸 XL" }));
    await user.click(screen.getByRole("button", { name: "颜色 蓝色" }));

    expect(screen.getByTestId("stock-status")).toHaveTextContent(
      "该组合不可选，请更换颜色或尺寸",
    );
    expect(screen.getByRole("button", { name: "加入购物车" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "尺寸 XL，缺货" }),
    ).toBeDisabled();
  });

  it("连续点击加入购物车只会发出一次 POST，并携带 Idempotency-Key", async () => {
    const postDeferred = createDeferred<Response>();
    const fetchMock = installFetchMock({ postResponse: postDeferred.promise });
    await renderLoadedApp();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "尺寸 M" }));
    await user.click(screen.getByRole("button", { name: "颜色 红色" }));

    const addButton = screen.getByRole("button", { name: "加入购物车" });
    fireEvent.click(addButton);
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(getPostCalls(fetchMock)).toHaveLength(1);
    });

    const postCall = getPostCalls(fetchMock)[0];
    expect(postCall).toBeDefined();
    if (!postCall) {
      throw new Error("未捕获到 POST 请求");
    }
    const requestHeaders = new Headers(postCall[1]?.headers);
    expect(requestHeaders.get("Idempotency-Key")).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
    const requestBody: unknown = JSON.parse(String(postCall[1]?.body));
    expect(requestBody).toEqual({ sku_id: "SKU-RED-M", quantity: 1 });
    expect(screen.getByRole("button", { name: /加入中/ })).toBeDisabled();

    // 第二次点击即使直接派发到同一个 DOM 节点，也会被同步锁拦截。
    fireEvent.click(addButton);
    expect(getPostCalls(fetchMock)).toHaveLength(1);

    postDeferred.resolve(new Response(null, { status: 201 }));
    await waitFor(() => {
      expect(screen.getByText(/已加入购物车/)).toBeInTheDocument();
    });
  });

  it("切换 SKU 后数量自动收敛到新库存上限", async () => {
    const user = userEvent.setup();
    installFetchMock();
    await renderLoadedApp();

    await user.click(screen.getByRole("button", { name: "尺寸 L" }));
    await user.click(screen.getByRole("button", { name: "颜色 红色" }));

    const decrease = screen.getByRole("button", { name: "减少数量" });
    const increase = screen.getByRole("button", { name: "增加数量" });

    await user.click(increase);
    await user.click(increase);
    await user.click(increase);
    expect(screen.getByLabelText("当前数量")).toHaveTextContent("4");
    expect(increase).toBeEnabled();

    // 蓝色 L 仅剩 1 件，原数量 4 应被重置为 1。
    await user.click(screen.getByRole("button", { name: "颜色 蓝色" }));
    expect(screen.getByLabelText("当前数量")).toHaveTextContent("1");
    expect(decrease).toBeDisabled();
    expect(increase).toBeDisabled();
  });

  it("商品请求失败时展示错误态，点击重试可以恢复", async () => {
    const user = userEvent.setup();
    installFetchMock({
      productResponses: [
        jsonResponse({ message: "商品服务暂时不可用。" }, 503),
      ],
    });
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "商品服务暂时不可用。",
    );

    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(
      await screen.findByRole("heading", { name: productResponseFixture.name }),
    ).toBeInTheDocument();
  });

  it("加购被库存不足打回后，会自己重新同步商品而不需要整页刷新", async () => {
    const user = userEvent.setup();

    // 第一次返回库存 3，服务端实际已经卖空（陈旧库存场景）。
    const staleProduct = structuredClone(productResponseFixture);
    const staleSku = staleProduct.skus.find((sku) => sku.id === "SKU-RED-M");
    if (staleSku) {
      staleSku.stock = 0;
      staleSku.available = false;
    }

    const fetchMock = installFetchMock({
      productResponses: [
        jsonResponse(productResponseFixture),
        jsonResponse(staleProduct),
      ],
      postResponse: Promise.resolve(
        jsonResponse(
          {
            error_code: "INSUFFICIENT_STOCK",
            message: "库存不足：SKU SKU-RED-M 仅剩 0 件，请求 1 件。",
          },
          400,
        ),
      ),
    });

    await renderLoadedApp();
    await user.click(screen.getByRole("button", { name: "尺寸 M" }));
    await user.click(screen.getByRole("button", { name: "颜色 红色" }));
    expect(screen.getByTestId("stock-status")).toHaveTextContent("库存 3 件");

    await user.click(screen.getByRole("button", { name: "加入购物车" }));

    expect(await screen.findByText(/库存不足/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("stock-status")).toHaveTextContent(
        "该组合暂时缺货",
      );
    });

    // 初次加载 + 失败后自愈，一共两次 GET 商品。
    expect(getProductGetCalls(fetchMock)).toHaveLength(2);
  });
});
