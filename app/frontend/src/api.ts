import type {
  AddCartItemPayload,
  Cart,
  CartItem,
  Product,
  ProductOption,
  ProductOptionValue,
  SKU,
} from "./types";

const API_BASE = "/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: string;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function toId(value: unknown): string | undefined {
  if (isNonEmptyString(value)) {
    return value;
  }
  if (isFiniteNumber(value)) {
    return String(value);
  }
  return undefined;
}

function invalidResponse(): ApiError {
  return new ApiError("服务端返回的数据格式不正确，请稍后重试。", 200);
}

function parseOptionValue(input: unknown): ProductOptionValue {
  if (!isRecord(input) || !isNonEmptyString(input.value)) {
    throw invalidResponse();
  }

  const label = isNonEmptyString(input.label) ? input.label : input.value;
  const parsed: ProductOptionValue = {
    value: input.value,
    label,
  };
  if (isNonEmptyString(input.swatch)) {
    parsed.swatch = input.swatch;
  }
  return parsed;
}

function parseOption(input: unknown): ProductOption {
  if (!isRecord(input) || !Array.isArray(input.values)) {
    throw invalidResponse();
  }

  // 当前后端使用 key，兼容其他可能使用 id 的实现。
  const optionId = toId(input.key) ?? toId(input.id);
  if (!optionId) {
    throw invalidResponse();
  }

  return {
    id: optionId,
    name: isNonEmptyString(input.name) ? input.name : optionId,
    values: input.values.map(parseOptionValue),
  };
}

function parseSkuOptions(
  input: Record<string, unknown>,
  productOptions: ProductOption[],
): Record<string, string> {
  const options: Record<string, string> = {};

  if (isRecord(input.options)) {
    for (const [key, value] of Object.entries(input.options)) {
      if (isNonEmptyString(value)) {
        options[key] = value;
      }
    }
    return options;
  }

  // 当前后端把颜色 / 尺寸平铺在 SKU 顶层，按 option.key 做映射。
  for (const option of productOptions) {
    const rawValue = input[option.id];
    if (isNonEmptyString(rawValue)) {
      options[option.id] = rawValue;
    }
  }

  return options;
}

function parseSku(input: unknown, productOptions: ProductOption[]): SKU {
  if (
    !isRecord(input) ||
    !isNonEmptyString(input.id) ||
    !isFiniteNumber(input.price) ||
    !isFiniteNumber(input.stock)
  ) {
    throw invalidResponse();
  }

  const sku: SKU = {
    id: input.id,
    options: parseSkuOptions(input, productOptions),
    price: input.price,
    stock: Math.max(0, Math.floor(input.stock)),
  };
  if (isNonEmptyString(input.code)) {
    sku.code = input.code;
  }
  if (isFiniteNumber(input.compareAtPrice)) {
    sku.compareAtPrice = input.compareAtPrice;
  }
  if (isNonEmptyString(input.image)) {
    sku.image = input.image;
  }
  return sku;
}

function parseProduct(input: unknown): Product {
  if (
    !isRecord(input) ||
    !isNonEmptyString(input.name) ||
    !isNonEmptyString(input.currency) ||
    !Array.isArray(input.options) ||
    !Array.isArray(input.skus)
  ) {
    throw invalidResponse();
  }

  const productId = toId(input.id);
  if (!productId) {
    throw invalidResponse();
  }

  const options = input.options.map(parseOption);
  const product: Product = {
    id: productId,
    name: input.name,
    description: isNonEmptyString(input.description) ? input.description : "",
    currency: input.currency,
    options,
    skus: input.skus.map((sku) => parseSku(sku, options)),
  };
  if (isNonEmptyString(input.subtitle)) {
    product.subtitle = input.subtitle;
  }
  if (isNonEmptyString(input.image)) {
    product.image = input.image;
  }
  if (Array.isArray(input.highlights)) {
    product.highlights = input.highlights.filter(isNonEmptyString);
  }
  return product;
}

function parseCartItem(input: unknown): CartItem {
  if (!isRecord(input)) {
    throw invalidResponse();
  }

  const skuId = toId(input.sku_id) ?? toId(input.skuId);
  const productId = toId(input.product_id) ?? toId(input.productId);
  if (!skuId || !productId || !isFiniteNumber(input.quantity)) {
    throw invalidResponse();
  }

  const item: CartItem = {
    id: skuId,
    skuId,
    productId,
    quantity: Math.max(0, Math.floor(input.quantity)),
  };
  if (isNonEmptyString(input.color)) {
    item.color = input.color;
  }
  if (isNonEmptyString(input.color_label)) {
    item.colorLabel = input.color_label;
  }
  if (isNonEmptyString(input.size)) {
    item.size = input.size;
  }
  const unitPrice = isFiniteNumber(input.unit_price)
    ? input.unit_price
    : isFiniteNumber(input.unitPrice)
      ? input.unitPrice
      : undefined;
  if (unitPrice !== undefined) {
    item.unitPrice = unitPrice;
  }
  const lineTotal = isFiniteNumber(input.line_total)
    ? input.line_total
    : isFiniteNumber(input.lineTotal)
      ? input.lineTotal
      : undefined;
  if (lineTotal !== undefined) {
    item.lineTotal = lineTotal;
  }
  return item;
}

function parseCart(input: unknown): Cart {
  if (!isRecord(input)) {
    throw invalidResponse();
  }

  const items = Array.isArray(input.items) ? input.items.map(parseCartItem) : [];
  const explicitTotal = isFiniteNumber(input.total_items)
    ? input.total_items
    : isFiniteNumber(input.totalQuantity)
      ? input.totalQuantity
      : isFiniteNumber(input.totalCount)
        ? input.totalCount
        : undefined;
  const totalAmount = isFiniteNumber(input.total_amount)
    ? input.total_amount
    : undefined;

  return {
    items,
    totalQuantity:
      explicitTotal ?? items.reduce((sum, item) => sum + item.quantity, 0),
    ...(totalAmount !== undefined ? { totalAmount } : {}),
  };
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text.trim().length === 0) {
    return null;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new ApiError("服务端返回了无法解析的数据。", response.status);
  }
}

function getProblemMessage(payload: unknown): string | undefined {
  if (!isRecord(payload)) {
    return undefined;
  }
  if (isNonEmptyString(payload.message)) {
    return payload.message;
  }
  if (isNonEmptyString(payload.error)) {
    return payload.error;
  }
  return undefined;
}

async function request(
  path: string,
  options: RequestOptions = {},
): Promise<Response> {
  const headers = new Headers({
    Accept: "application/json",
    ...options.headers,
  });
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body,
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError("网络连接失败，请检查网络后重试。", 0);
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await readJson(response);
    } catch {
      // 错误响应体的解析失败不应覆盖更有意义的 HTTP 状态错误。
    }
    throw new ApiError(
      getProblemMessage(payload) ?? `请求失败（HTTP ${response.status}）。`,
      response.status,
    );
  }

  return response;
}

export async function fetchProduct(
  productId: string,
  signal?: AbortSignal,
): Promise<Product> {
  const response = await request(`/products/${encodeURIComponent(productId)}`, {
    signal,
  });
  return parseProduct(await readJson(response));
}

export async function fetchCart(signal?: AbortSignal): Promise<Cart> {
  const response = await request("/cart", { signal });
  return parseCart(await readJson(response));
}

export async function addCartItem(
  payload: AddCartItemPayload,
  idempotencyKey: string,
): Promise<void> {
  await request("/cart/items", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({
      sku_id: payload.skuId,
      quantity: payload.quantity,
    }),
  });
}
