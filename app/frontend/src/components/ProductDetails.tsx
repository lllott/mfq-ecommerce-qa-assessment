import { useEffect, useMemo, useState } from "react";
import type { Product, SelectedOptions } from "../types";
import { formatPrice } from "../utils/format";
import {
  findSku,
  getPriceRange,
  getSelectedOptionLabel,
  getSelectionState,
  getStockStatusLabel,
  getMaxQuantity,
} from "../utils/variant";
import { AddToCart } from "./AddToCart";
import { ProductGallery } from "./ProductGallery";
import { QuantityStepper } from "./QuantityStepper";
import { SkuSelector } from "./SkuSelector";

interface ProductDetailsProps {
  product: Product;
  onCartChanged: () => void;
  /** 服务端库存与页面不一致时，重新拉取商品让页面自愈。 */
  onRefreshProduct: () => void;
}

export function ProductDetails({
  product,
  onCartChanged,
  onRefreshProduct,
}: ProductDetailsProps) {
  const [selected, setSelected] = useState<SelectedOptions>({});
  const [quantity, setQuantity] = useState(1);

  const selectedSku = useMemo(
    () => findSku(product, selected),
    [product, selected],
  );
  const selectionState = getSelectionState(product, selected, selectedSku);
  const maxQuantity = getMaxQuantity(selectedSku);
  const displayQuantity =
    maxQuantity > 0 ? Math.min(quantity, maxQuantity) : 1;

  // 切换 SKU 后，如果原数量超过新库存，立即收敛到新库存。
  useEffect(() => {
    if (quantity !== displayQuantity) {
      setQuantity(displayQuantity);
    }
  }, [quantity, displayQuantity]);

  const priceRange = getPriceRange(product);
  const priceText = selectedSku
    ? formatPrice(selectedSku.price, product.currency)
    : product.skus.length > 0
      ? `${formatPrice(priceRange.min, product.currency)} 起`
      : "暂未定价";

  const compareAtPrice =
    selectedSku?.compareAtPrice !== undefined &&
    selectedSku.compareAtPrice > selectedSku.price
      ? formatPrice(selectedSku.compareAtPrice, product.currency)
      : null;

  const selectedColor = getSelectedOptionLabel(
    product,
    "color",
    selected,
  );
  const selectedSize = getSelectedOptionLabel(product, "size", selected);
  const selectionSummary =
    selectedColor && selectedSize
      ? `${selectedColor} / ${selectedSize}`
      : "尚未选择完整规格";

  function handleSelect(optionId: string, value: string): void {
    setSelected((current) => ({ ...current, [optionId]: value }));
  }

  function handleQuantityChange(nextQuantity: number): void {
    const upperBound = Math.max(maxQuantity, 1);
    setQuantity(Math.min(Math.max(nextQuantity, 1), upperBound));
  }

  return (
    <article className="pdp">
      <ProductGallery product={product} sku={selectedSku} />

      <div className="product-info">
        <div className="product-heading">
          <p className="eyebrow">STILL / COTTON ESSENTIALS</p>
          <h1 className="product-title">{product.name}</h1>
          {product.subtitle ? (
            <p className="product-subtitle">{product.subtitle}</p>
          ) : null}
        </div>

        <div className="price-area">
          <p className="price" data-testid="product-price">
            {priceText}
          </p>
          {compareAtPrice ? (
            <p className="compare-price">
              <span className="sr-only">原价</span>
              {compareAtPrice}
            </p>
          ) : null}
        </div>

        <p
          className={`stock-status ${
            selectionState === "out_of_stock" || selectionState === "invalid"
              ? "stock-status--out"
              : ""
          }`}
          role="status"
          aria-live="polite"
          data-testid="stock-status"
        >
          {getStockStatusLabel(selectionState, selectedSku)}
          {selectedSku?.code ? (
            <span className="sku-code"> · {selectedSku.code}</span>
          ) : null}
        </p>

        <div className="section-rule" />

        <div className="selection-meta">
          <span>已选规格</span>
          <strong>{selectionSummary}</strong>
        </div>

        <SkuSelector
          product={product}
          selected={selected}
          onSelect={handleSelect}
        />

        <QuantityStepper
          quantity={displayQuantity}
          maxQuantity={maxQuantity}
          onChange={handleQuantityChange}
        />

        <AddToCart
          sku={selectedSku}
          quantity={displayQuantity}
          selectionState={selectionState}
          onAdded={onCartChanged}
          onStaleStock={onRefreshProduct}
        />

        {product.highlights && product.highlights.length > 0 ? (
          <ul className="highlight-list" aria-label="商品卖点">
            {product.highlights.map((highlight) => (
              <li key={highlight}>{highlight}</li>
            ))}
          </ul>
        ) : null}

        <div className="service-notes">
          <div>
            <span className="service-mark" aria-hidden="true">
              01
            </span>
            <p>顺丰发货，预计 2–4 个工作日送达。</p>
          </div>
          <div>
            <span className="service-mark" aria-hidden="true">
              02
            </span>
            <p>吊牌完好支持 7 天无理由退换。</p>
          </div>
        </div>

        <details className="product-description" open>
          <summary>商品说明</summary>
          <p>{product.description}</p>
        </details>
      </div>
    </article>
  );
}
