import { useCallback, useEffect, useRef, useState } from "react";
import { fetchCart } from "../api";
import type { Cart } from "../types";
import { getErrorMessage } from "../utils/format";

interface UseCartResult {
  cart: Cart | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
  retry: () => void;
}

export function useCart(): UseCartResult {
  const [cart, setCart] = useState<Cart | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const loadCart = useCallback(async (signal?: AbortSignal) => {
    const requestId = ++requestIdRef.current;
    setIsLoading(true);
    setError(null);

    try {
      const nextCart = await fetchCart(signal);
      if (requestId !== requestIdRef.current) {
        return;
      }
      setCart(nextCart);
    } catch (requestError: unknown) {
      if (
        requestId !== requestIdRef.current ||
        (requestError instanceof DOMException &&
          requestError.name === "AbortError")
      ) {
        return;
      }
      setError(getErrorMessage(requestError));
    } finally {
      if (requestId === requestIdRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadCart(controller.signal);
    return () => {
      controller.abort();
      requestIdRef.current += 1;
    };
  }, [loadCart]);

  const refresh = useCallback(() => {
    void loadCart();
  }, [loadCart]);

  const retry = useCallback(() => {
    void loadCart();
  }, [loadCart]);

  return { cart, isLoading, error, refresh, retry };
}
