import { useId, useRef, useState } from "react";
import { ApiError, addCartItem } from "../api";
import type { SKU } from "../types";
import type { SelectionState } from "../utils/variant";
import { getErrorMessage } from "../utils/format";
import { createIdempotencyKey } from "../utils/idempotency";

interface AddToCartProps {
  sku: SKU | undefined;
  quantity: number;
  selectionState: SelectionState;
  onAdded: () => void;
  /** 加购被 400 打回时调用，用于重新同步服务端库存。 */
  onStaleStock: () => void;
}

type Feedback =
  | { kind: "idle" }
  | { kind: "success"; message: string }
  | { kind: "error"; message: string };

export function AddToCart({
  sku,
  quantity,
  selectionState,
  onAdded,
  onStaleStock,
}: AddToCartProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>({ kind: "idle" });
  const submittingRef = useRef(false);
  const hintId = useId();
  const feedbackId = useId();

  const isInStock = selectionState === "available";
  const isDisabled = !isInStock || isSubmitting;

  let hint = "请先选择颜色和尺寸。";
  if (isInStock) {
    hint = "支持 7 天无理由退换，满 ¥299 免运费。";
  } else if (selectionState === "invalid") {
    hint = "该组合不可选，请更换颜色或尺寸。";
  } else if (selectionState === "out_of_stock") {
    hint = "该组合暂时缺货，请更换颜色或尺寸。";
  }

  async function submitAddToCart(): Promise<void> {
    // ref 的同步保护可以挡住同一事件循环内的连点，
    // 不依赖 React 状态更新完成后再禁用按钮。
    if (submittingRef.current || !sku || sku.stock <= 0) {
      return;
    }

    submittingRef.current = true;
    setIsSubmitting(true);
    setFeedback({ kind: "idle" });

    try {
      const idempotencyKey = createIdempotencyKey();
      await addCartItem(
        {
          skuId: sku.id,
          quantity,
        },
        idempotencyKey,
      );
      setFeedback({
        kind: "success",
        message: `已加入购物车：${quantity} 件。`,
      });
      onAdded();
    } catch (error: unknown) {
      setFeedback({ kind: "error", message: getErrorMessage(error) });
      // 400 通常意味着服务端库存比页面缓存的更少（陈旧库存）。
      // 这里顺手重新拉一次商品，让页面自愈，用户不必整页刷新。
      if (error instanceof ApiError && error.status === 400) {
        onStaleStock();
      }
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }

  return (
    <div className="add-to-cart">
      <button
        className="add-button"
        type="button"
        disabled={isDisabled}
        aria-busy={isSubmitting}
        aria-describedby={`${hintId} ${feedbackId}`}
        onClick={() => {
          void submitAddToCart();
        }}
      >
        {isSubmitting ? (
          <>
            <span className="spinner" aria-hidden="true" />
            加入中…
          </>
        ) : (
          "加入购物车"
        )}
      </button>

      <p className="add-hint" id={hintId}>
        {hint}
      </p>

      <div className="feedback-region" id={feedbackId}>
        {feedback.kind === "success" ? (
          <p className="feedback feedback--success" role="status">
            <span className="feedback-icon" aria-hidden="true">
              ✓
            </span>
            {feedback.message}
          </p>
        ) : null}

        {feedback.kind === "error" ? (
          <div className="feedback feedback--error" role="alert">
            <p>{feedback.message}</p>
            <button
              className="feedback-retry"
              type="button"
              disabled={isSubmitting}
              onClick={() => {
                void submitAddToCart();
              }}
            >
              重试
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
