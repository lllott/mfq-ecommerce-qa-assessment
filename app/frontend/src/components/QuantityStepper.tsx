interface QuantityStepperProps {
  quantity: number;
  maxQuantity: number;
  onChange: (quantity: number) => void;
}

export function QuantityStepper({
  quantity,
  maxQuantity,
  onChange,
}: QuantityStepperProps) {
  const hasStock = maxQuantity > 0;
  const canDecrease = hasStock && quantity > 1;
  const canIncrease = hasStock && quantity < maxQuantity;

  return (
    <div className="quantity-row">
      <div className="quantity-label-wrap">
        <span className="quantity-label" id="quantity-label">
          数量
        </span>
        <span className="quantity-hint">
          {hasStock ? `最多 ${maxQuantity} 件` : "当前规格暂不可购买"}
        </span>
      </div>

      <div
        className="quantity-stepper"
        role="group"
        aria-labelledby="quantity-label"
      >
        <button
          className="quantity-button"
          type="button"
          aria-label="减少数量"
          disabled={!canDecrease}
          onClick={() => {
            onChange(quantity - 1);
          }}
        >
          <span aria-hidden="true">−</span>
        </button>
        <span className="quantity-value" aria-live="polite" aria-label="当前数量">
          {quantity}
        </span>
        <button
          className="quantity-button"
          type="button"
          aria-label="增加数量"
          disabled={!canIncrease}
          onClick={() => {
            onChange(quantity + 1);
          }}
        >
          <span aria-hidden="true">+</span>
        </button>
      </div>
    </div>
  );
}
