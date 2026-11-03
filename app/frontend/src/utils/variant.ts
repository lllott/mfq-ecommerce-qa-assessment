import type { Product, ProductOption, SKU, SelectedOptions } from "../types";

export const COLOR_OPTION_ID = "color";
export const SIZE_OPTION_ID = "size";

function skuMatches(sku: SKU, constraints: SelectedOptions): boolean {
  return Object.entries(constraints).every(
    ([optionId, optionValue]) => sku.options[optionId] === optionValue,
  );
}

/**
 * 根据已选维度精确解析 SKU。
 * 只有每个商品维度都被选中，且存在完全匹配的 SKU 时才会返回结果。
 */
export function findSku(
  product: Product,
  selected: SelectedOptions,
): SKU | undefined {
  const allDimensionsSelected = product.options.every(
    (option) => selected[option.id] !== undefined,
  );
  if (!allDimensionsSelected) {
    return undefined;
  }

  return product.skus.find((sku) => skuMatches(sku, selected));
}

/** 返回当前 SKU 的最大可购数量；缺货 / 未选完整时返回 0。 */
export function getMaxQuantity(sku: SKU | undefined): number {
  return sku && sku.stock > 0 ? sku.stock : 0;
}

/**
 * 判断某个选项按钮是否应该置灰。
 *
 * - 颜色：只要该颜色还有任意尺寸有货，就保持可切换。否则用户无法切换颜色，
 *   也就无法看到“当前尺寸缺货”的明确反馈。
 * - 尺寸：结合当前已选颜色，精确判断该组合是否有货，缺货则禁用。
 * - 其他自定义维度：结合除自身外的全部已选维度判断。
 *
 * 未选颜色时，尺寸按其全局是否有货判断。
 */
export function isOptionValueUnavailable(
  product: Product,
  option: ProductOption,
  value: string,
  selected: SelectedOptions,
): boolean {
  const available = product.skus.some((sku) => {
    if (sku.stock <= 0 || sku.options[option.id] !== value) {
      return false;
    }

    if (option.id === COLOR_OPTION_ID) {
      // 颜色选项不跟随当前尺寸禁用，避免用户被困在缺货尺寸里。
      return true;
    }

    const constraints: SelectedOptions = { [option.id]: value };
    if (selected[COLOR_OPTION_ID] !== undefined) {
      constraints[COLOR_OPTION_ID] = selected[COLOR_OPTION_ID];
    }

    // 除当前维度外的其他维度也参与匹配。
    for (const other of product.options) {
      if (other.id === option.id || other.id === COLOR_OPTION_ID) {
        continue;
      }
      const selectedValue = selected[other.id];
      if (selectedValue !== undefined) {
        constraints[other.id] = selectedValue;
      }
    }

    return skuMatches(sku, constraints);
  });

  return !available;
}

export type SelectionState =
  | "incomplete"
  | "invalid"
  | "out_of_stock"
  | "available";

/**
 * 判断当前选择的四种状态，把「没选完」「组合不存在」「组合缺货」区分开：
 * - incomplete：还有维度没选；
 * - invalid：维度都选了，但该组合根本没有 SKU（例如没有「蓝色 XL」）；
 * - out_of_stock：组合存在，但库存为 0；
 * - available：可以加购。
 */
export function getSelectionState(
  product: Product,
  selected: SelectedOptions,
  sku: SKU | undefined,
): SelectionState {
  const allSelected = product.options.every(
    (option) => selected[option.id] !== undefined,
  );
  if (!allSelected) {
    return "incomplete";
  }
  if (!sku) {
    return "invalid";
  }
  if (sku.stock <= 0) {
    return "out_of_stock";
  }
  return "available";
}

/** 按选择状态给出库存文案。 */
export function getStockStatusLabel(
  state: SelectionState,
  sku: SKU | undefined,
): string {
  switch (state) {
    case "incomplete":
      return "请选择完整规格查看库存";
    case "invalid":
      return "该组合不可选，请更换颜色或尺寸";
    case "out_of_stock":
      return "该组合暂时缺货";
    case "available":
      return `库存 ${sku ? sku.stock : 0} 件`;
  }
}

/** 展示价格区间，用于用户尚未选完整规格时。 */
export function getPriceRange(product: Product): { min: number; max: number } {
  const prices = product.skus.map((sku) => sku.price);
  if (prices.length === 0) {
    return { min: 0, max: 0 };
  }
  return {
    min: Math.min(...prices),
    max: Math.max(...prices),
  };
}

export function getSelectedOptionLabel(
  product: Product,
  optionId: string,
  selected: SelectedOptions,
): string | undefined {
  const option = product.options.find((item) => item.id === optionId);
  const selectedValue = selected[optionId];
  return option?.values.find((value) => value.value === selectedValue)?.label;
}
