interface HeaderProps {
  cartCount: number;
  isCartLoading: boolean;
  cartError: string | null;
  onRetryCart: () => void;
}

export function Header({
  cartCount,
  isCartLoading,
  cartError,
  onRetryCart,
}: HeaderProps) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <a className="brand" href="/" aria-label="STILL 商店首页">
          <span className="brand-mark" aria-hidden="true">
            S
          </span>
          <span className="brand-name">STILL</span>
        </a>

        <p className="header-note">轻盈生活 · 免费配送</p>

        <div className="cart-area">
          {cartError ? (
            <button
              className="cart-retry"
              type="button"
              onClick={onRetryCart}
              aria-label="购物车同步失败，点击重试"
            >
              <span aria-hidden="true">!</span>
              重试同步
            </button>
          ) : (
            <div
              className="cart-pill"
              role="status"
              aria-live="polite"
              aria-label={`购物车，共 ${cartCount} 件商品`}
            >
              <svg
                className="cart-icon"
                aria-hidden="true"
                viewBox="0 0 24 24"
                width="20"
                height="20"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="9" cy="20" r="1.2" />
                <circle cx="18" cy="20" r="1.2" />
                <path d="M3 4h2l2.2 10.2a1.5 1.5 0 0 0 1.5 1.2h8.9a1.5 1.5 0 0 0 1.5-1.2L21 7H6" />
              </svg>
              <span className="cart-label">购物车</span>
              <span className="cart-count">
                {isCartLoading ? "…" : cartCount}
              </span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
