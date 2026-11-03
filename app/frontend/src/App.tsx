import { ErrorState } from "./components/ErrorState";
import { Header } from "./components/Header";
import { ProductDetails } from "./components/ProductDetails";
import { useCart } from "./hooks/useCart";
import { useProduct } from "./hooks/useProduct";

const PRODUCT_ID = import.meta.env.VITE_PRODUCT_ID?.trim() || "tee-001";

function ProductSkeleton() {
  return (
    <div className="skeleton-layout" aria-hidden="true">
      <div className="skeleton skeleton-image" />
      <div className="skeleton-copy">
        <div className="skeleton skeleton-line skeleton-line--short" />
        <div className="skeleton skeleton-line skeleton-line--title" />
        <div className="skeleton skeleton-line skeleton-line--medium" />
        <div className="skeleton skeleton-line skeleton-line--price" />
        <div className="skeleton skeleton-block" />
      </div>
    </div>
  );
}

export default function App() {
  const {
    product,
    isLoading: isProductLoading,
    error: productError,
    retry: retryProduct,
    refresh: refreshProduct,
  } = useProduct(PRODUCT_ID);
  const {
    cart,
    isLoading: isCartLoading,
    error: cartError,
    refresh: refreshCart,
    retry: retryCart,
  } = useCart();

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到商品详情
      </a>

      <Header
        cartCount={cart?.totalQuantity ?? 0}
        isCartLoading={isCartLoading}
        cartError={cartError}
        onRetryCart={retryCart}
      />

      <main
        className="page-container"
        id="main-content"
        tabIndex={-1}
        aria-busy={isProductLoading}
      >
        {isProductLoading ? (
          <>
            <p className="sr-only" role="status">
              正在加载商品…
            </p>
            <ProductSkeleton />
          </>
        ) : null}

        {!isProductLoading && productError ? (
          <ErrorState
            title="商品加载失败"
            message={productError}
            onRetry={retryProduct}
          />
        ) : null}

        {!isProductLoading && product ? (
          <ProductDetails
            product={product}
            onCartChanged={refreshCart}
            onRefreshProduct={() => {
              void refreshProduct();
            }}
          />
        ) : null}
      </main>

      <footer className="site-footer">
        <p>STILL — 为日常留一点呼吸感。</p>
        <p>© 2026 STILL STUDIO</p>
      </footer>
    </div>
  );
}
