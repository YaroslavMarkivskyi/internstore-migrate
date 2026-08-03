import { useState } from 'react';

import {
  SliderContainer,
  SliderWrapper,
  StyledSlider,
  ValueDisplay,
  ValueText,
} from './styles';

export interface RangeSliderProps {
  /**
   * Minimum value of the range
   */
  min: number;

  /**
   * Maximum value of the range
   */
  max: number;

  /**
   * Initial value of the range
   */
  defaultValue?: [number, number];

  /**
   * Step size between values
   */
  step?: number;

  /**
   * Prefix for displayed values (e.g. "$")
   */
  prefix?: string;

  /**
   * Suffix for displayed values (e.g. " items")
   */
  suffix?: string;

  /**
   * Callback when value changes
   */
  onChange?: (value: [number, number]) => void;

  /**
   * Optional custom color for the slider track
   */
  trackColor?: string;

  /**
   * Optional disabled state
   */
  disabled?: boolean;
}

/**
 * RangeSlider component displays a slider with two thumbs and value displays at both ends
 */
const RangeSlider = ({
  min,
  max,
  defaultValue = [min, max],
  step = 1,
  prefix = '',
  suffix = '',
  onChange,
  trackColor,
  disabled = false,
}: RangeSliderProps) => {
  const [value, setValue] = useState<[number, number]>(defaultValue);

  const handleChange = (_event: Event, newValue: number | number[]) => {
    if (Array.isArray(newValue)) {
      const typedValue: [number, number] = [newValue[0], newValue[1]];
      setValue(typedValue);
      if (onChange) {
        onChange(typedValue);
      }
    }
  };

  const formatValue = (val: number) => {
    return `${prefix}${val}${suffix}`;
  };

  return (
    <SliderContainer>
      <ValueDisplay>
        <ValueText>{formatValue(value[0])}</ValueText>
      </ValueDisplay>

      <SliderWrapper>
        <StyledSlider
          value={value}
          onChange={handleChange}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          sx={trackColor ? { color: trackColor } : {}}
        />
      </SliderWrapper>

      <ValueDisplay>
        <ValueText>{formatValue(value[1])}</ValueText>
      </ValueDisplay>
    </SliderContainer>
  );
};

export default RangeSlider;
