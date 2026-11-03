import { useCallback, useEffect, useState } from "react";
import { fetchProduct } from "../api";
import type { Product } from "../types";
import { getErrorMessage } from "../utils/format";

interface UseProductResult {
  product: Product | null;
  isLoading: boolean;
  error: string | null;
  retry: () => void;
  /** 软刷新：不进入骨架屏，成功后原地替换商品数据。 */
  refresh: () => Promise<void>;
}

export function useProduct(productId: string): UseProductResult {
  const [product, setProduct] = useState<Product | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let isActive = true;

    setIsLoading(true);
    setError(null);
    setProduct(null);

    fetchProduct(productId, controller.signal)
      .then((data) => {
        if (!isActive) {
          return;
        }
        setProduct(data);
      })
      .catch((requestError: unknown) => {
        if (
          !isActive ||
          (requestError instanceof DOMException &&
            requestError.name === "AbortError")
        ) {
          return;
        }
        setError(getErrorMessage(requestError));
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
      controller.abort();
    };
  }, [productId, reloadKey]);

  const retry = useCallback(() => {
    setReloadKey((key) => key + 1);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchProduct(productId);
      setProduct(data);
      setError(null);
    } catch {
      // 刷新失败时保留页面已有内容，用户可以继续操作或手动重试。
    }
  }, [productId]);

  return { product, isLoading, error, retry, refresh };
}
