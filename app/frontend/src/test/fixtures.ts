/**
 * 与当前 FastAPI 后端一致的原始响应夹具。
 * 前端会在 api.ts 中把 options[].key / SKU 的扁平分维度规范化为内部模型。
 *
 * 覆盖两类边界：
 *   - 「蓝色 XL」没有 SKU —— 不可用组合；
 *   - 「红色 S」stock 为 0 —— 缺货 SKU。
 */
export const productResponseFixture = {
  id: "tee-001",
  name: "云感纯棉圆领 T 恤",
  description: "260g 精梳棉，宽松版型，日常百搭。",
  currency: "CNY",
  options: [
    {
      key: "color",
      name: "颜色",
      values: [
        { value: "red", label: "红色" },
        { value: "blue", label: "蓝色" },
      ],
    },
    {
      key: "size",
      name: "尺寸",
      values: [
        { value: "S", label: "S" },
        { value: "M", label: "M" },
        { value: "L", label: "L" },
        { value: "XL", label: "XL" },
      ],
    },
  ],
  skus: [
    {
      id: "SKU-RED-S",
      color: "red",
      color_label: "红色",
      size: "S",
      price: 89,
      stock: 0,
      available: false,
      image: "/images/tee-red.svg",
    },
    {
      id: "SKU-RED-M",
      color: "red",
      color_label: "红色",
      size: "M",
      price: 99,
      stock: 3,
      available: true,
      image: "/images/tee-red.svg",
    },
    {
      id: "SKU-RED-L",
      color: "red",
      color_label: "红色",
      size: "L",
      price: 109,
      stock: 5,
      available: true,
      image: "/images/tee-red.svg",
    },
    {
      id: "SKU-RED-XL",
      color: "red",
      color_label: "红色",
      size: "XL",
      price: 119,
      stock: 2,
      available: true,
      image: "/images/tee-red.svg",
    },
    {
      id: "SKU-BLUE-S",
      color: "blue",
      color_label: "蓝色",
      size: "S",
      price: 99,
      stock: 4,
      available: true,
      image: "/images/tee-blue.svg",
    },
    {
      id: "SKU-BLUE-M",
      color: "blue",
      color_label: "蓝色",
      size: "M",
      price: 109,
      stock: 2,
      available: true,
      image: "/images/tee-blue.svg",
    },
    {
      id: "SKU-BLUE-L",
      color: "blue",
      color_label: "蓝色",
      size: "L",
      price: 119,
      stock: 1,
      available: true,
      image: "/images/tee-blue.svg",
    },
  ],
};

export const cartResponseFixture = {
  items: [
    {
      sku_id: "SKU-RED-M",
      product_id: "tee-001",
      color: "red",
      color_label: "红色",
      size: "M",
      unit_price: 99,
      quantity: 2,
      line_total: 198,
    },
  ],
  total_items: 2,
  total_amount: 198,
};
