/**
 * 前端内部使用的商品 / 购物车数据结构。
 *
 * 后端原始响应会在 src/api.ts 中做一次规范化：
 * - options[].key -> options[].id
 * - SKU 的 color / size 字段 -> SKU.options
 * - cart.total_items -> totalQuantity
 * 这样组件层只依赖稳定的内部模型。
 */

export interface ProductOptionValue {
  /** 稳定值，用于和 SKU.options 匹配，例如 "red" */
  value: string;
  /** 展示文案，例如 "红色" */
  label: string;
  /** 颜色色块（CSS 颜色值）；可选 */
  swatch?: string;
}

export interface ProductOption {
  /** "color" | "size"；由后端 option.key 规范化而来 */
  id: string;
  /** 分组标题，例如 "颜色" / "尺寸" */
  name: string;
  values: ProductOptionValue[];
}

export type SelectedOptions = Record<string, string>;

export interface SKU {
  id: string;
  /** 仓库编码，可选展示 */
  code?: string;
  /** optionId -> optionValue，例如 { color: "red", size: "M" } */
  options: SelectedOptions;
  /** 商品金额，单位元 */
  price: number;
  /** 划线原价，单位元；后端当前未返回 */
  compareAtPrice?: number;
  /** 可售库存；0 表示缺货 */
  stock: number;
  /** 该 SKU 对应的主图；缺省时回退到商品主图 / 颜色图 */
  image?: string;
}

export interface Product {
  /** 与后端保持一致，例如 "tee-001" */
  id: string;
  name: string;
  subtitle?: string;
  description: string;
  /** ISO 4217 币种，例如 CNY */
  currency: string;
  /** 商品默认主图；后端当前未返回时由前端按颜色回退 */
  image?: string;
  options: ProductOption[];
  skus: SKU[];
  /** 商品卖点，可选 */
  highlights?: string[];
}

export interface CartItem {
  /** 后端没有独立行 id，使用 sku_id 作为前端行标识 */
  id: string;
  skuId: string;
  productId: string;
  quantity: number;
  color?: string;
  colorLabel?: string;
  size?: string;
  unitPrice?: number;
  lineTotal?: number;
}

export interface Cart {
  items: CartItem[];
  /** 购物车内商品总件数 */
  totalQuantity: number;
  totalAmount?: number;
}

/**
 * 前端提交给 api.ts 的加购参数。
 * 后端只接受 sku_id + quantity，价格和商品 id 均由服务端根据 SKU 决定。
 */
export interface AddCartItemPayload {
  skuId: string;
  quantity: number;
}

/** 用于把未知的错误响应收窄为可读信息 */
export interface ApiProblem {
  message?: string;
  error?: string;
  error_code?: string;
}
