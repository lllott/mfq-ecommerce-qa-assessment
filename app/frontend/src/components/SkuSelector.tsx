import type { Product, SelectedOptions } from "../types";
import {
  COLOR_OPTION_ID,
  isOptionValueUnavailable,
} from "../utils/variant";

interface SkuSelectorProps {
  product: Product;
  selected: SelectedOptions;
  onSelect: (optionId: string, value: string) => void;
}

// 后端选项未携带色值时，给常见颜色一个展示色块。
const FALLBACK_SWATCHES: Record<string, string> = {
  red: "#b6463e",
  blue: "#506b8e",
  black: "#262624",
  white: "#f1ede5",
  gray: "#8c918d",
  grey: "#8c918d",
  green: "#526b56",
  beige: "#d8cbb8",
};

export function SkuSelector({
  product,
  selected,
  onSelect,
}: SkuSelectorProps) {
  return (
    <div className="sku-selector">
      {product.options.map((option) => {
        const selectedValue = selected[option.id];
        const selectedLabel = option.values.find(
          (value) => value.value === selectedValue,
        )?.label;
        const isColorOption = option.id === COLOR_OPTION_ID;

        return (
          <fieldset className="option-group" key={option.id}>
            <legend className="option-heading">
              <span>{option.name}</span>
              <span className="option-current">
                {selectedLabel ?? "请选择"}
              </span>
            </legend>
            <div
              className={`option-list ${
                isColorOption ? "option-list--colors" : ""
              }`}
            >
              {option.values.map((value) => {
                const isSelected = selectedValue === value.value;
                const isUnavailable = isOptionValueUnavailable(
                  product,
                  option,
                  value.value,
                  selected,
                );
                const accessibleLabel = `${option.name} ${value.label}${
                  isUnavailable ? "，缺货" : ""
                }`;

                return (
                  <button
                    key={value.value}
                    type="button"
                    className={`option-button ${
                      isColorOption ? "option-button--color" : ""
                    } ${isSelected ? "is-selected" : ""} ${
                      isUnavailable ? "is-unavailable" : ""
                    }`}
                    aria-label={accessibleLabel}
                    aria-pressed={isSelected}
                    disabled={isUnavailable}
                    onClick={() => {
                      onSelect(option.id, value.value);
                    }}
                  >
                    {isColorOption ? (
                      <span
                        className="color-swatch"
                        style={{
                          backgroundColor:
                            value.swatch ??
                            FALLBACK_SWATCHES[value.value] ??
                            "#c9c4b9",
                        }}
                        aria-hidden="true"
                      />
                    ) : null}
                    <span>{value.label}</span>
                  </button>
                );
              })}
            </div>
          </fieldset>
        );
      })}
    </div>
  );
}
