import { useEffect, useState } from "react";
import type { Product, SKU } from "../types";
import { getSelectedOptionLabel } from "../utils/variant";

interface ProductGalleryProps {
  product: Product;
  sku: SKU | undefined;
}

// 后端为每个 SKU 返回 image；万一缺失，再按颜色回退到本地演示图。
const COLOR_IMAGES: Record<string, string> = {
  red: "/images/tee-red.svg",
  blue: "/images/tee-blue.svg",
};
const DEFAULT_IMAGE = "/images/tee-red.svg";

export function ProductGallery({ product, sku }: ProductGalleryProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const selectedColor = sku?.options.color;
  const colorImage = selectedColor ? COLOR_IMAGES[selectedColor] : undefined;
  const image =
    sku?.image ?? colorImage ?? product.image ?? DEFAULT_IMAGE;
  const colorLabel = getSelectedOptionLabel(product, "color", sku?.options ?? {});
  const sizeLabel = getSelectedOptionLabel(product, "size", sku?.options ?? {});
  const variantLabel = [colorLabel, sizeLabel].filter(Boolean).join("，");
  const imageAlt = variantLabel
    ? `${product.name}，${variantLabel}`
    : `${product.name}商品图`;

  useEffect(() => {
    setImageFailed(false);
  }, [image]);

  return (
    <section className="product-gallery" aria-label="商品图片">
      <div className="gallery-frame">
        {imageFailed ? (
          <div className="gallery-fallback" role="img" aria-label={`${product.name}图片暂不可用`}>
            <span aria-hidden="true">STILL</span>
            <p>图片暂时无法加载</p>
          </div>
        ) : (
          <img
            key={image}
            className="gallery-image"
            src={image}
            alt={imageAlt}
            onError={() => {
              setImageFailed(true);
            }}
          />
        )}

        {sku && sku.stock <= 0 ? (
          <span className="gallery-badge">暂时缺货</span>
        ) : null}
      </div>
      <p className="gallery-footnote">
        实物颜色可能因屏幕显示略有差异
      </p>
    </section>
  );
}
