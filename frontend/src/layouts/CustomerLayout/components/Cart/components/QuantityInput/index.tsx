import { ChangeEvent, FC, useCallback, useEffect, useState } from 'react';

import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import { Box, debounce } from '@mui/material';

import colors from '@constants/colors';
import {
  ControlsButton,
  QuantityInputBase,
  Wrapper,
} from '@layouts/CustomerLayout/components/Cart/components/QuantityInput/styles';

import { useCart } from '../../../../../../hooks/useCart';

const MAX_QUANTITY = 999;
const MIN_QUANTITY = 1;

interface QuantityInputProps {
  onChange: (quantity: number) => void;
  defaultValue: number;
  productPrice: string;
}

const QuantityInput: FC<QuantityInputProps> = ({
  defaultValue,
  onChange,
  productPrice,
}) => {
  const [value, setValue] = useState(defaultValue);
  const { calculateEstimatedTotal, setEstimatedTotalCost } = useCart();

  const debouncedOnChange = useCallback(debounce(onChange, 1200), []);

  const updateQuantity = (newValue: number) => {
    if (newValue >= MIN_QUANTITY && newValue <= MAX_QUANTITY) {
      const oldQty = value;
      setValue(newValue);
      const newTotal = calculateEstimatedTotal(
        oldQty,
        newValue,
        parseFloat(productPrice)
      );
      setEstimatedTotalCost(newTotal);
      debouncedOnChange(newValue);
    }
  };

  const handleIncrement = () => {
    updateQuantity(Math.min(value + 1, MAX_QUANTITY));
  };

  const handleDecrement = () => {
    updateQuantity(Math.max(MIN_QUANTITY, value - 1));
  };

  const handleChange = (
    e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const newVal = e.target.value === '' ? 1 : parseInt(e.target.value, 10);
    if (!isNaN(newVal)) {
      updateQuantity(newVal);
    }
  };

  useEffect(() => {
    return () => {
      debouncedOnChange.clear();
    };
  }, [debouncedOnChange]);

  return (
    <Wrapper>
      <Box>
        <ControlsButton
          onClick={handleDecrement}
          disabled={value === MIN_QUANTITY}
          data-testid={'-quantity'}
        >
          <RemoveIcon
            sx={{
              fill:
                value === MIN_QUANTITY ? 'inherit' : colors.secondary.accent100,
            }}
          />
        </ControlsButton>
      </Box>
      <QuantityInputBase onChange={handleChange} value={value} />
      <Box>
        <ControlsButton
          onClick={handleIncrement}
          disabled={value === MAX_QUANTITY}
          data-testid={'+quantity'}
        >
          <AddIcon
            sx={{
              fill:
                value === MAX_QUANTITY ? 'inherit' : colors.secondary.accent100,
            }}
          />
        </ControlsButton>
      </Box>
    </Wrapper>
  );
};

export default QuantityInput;
