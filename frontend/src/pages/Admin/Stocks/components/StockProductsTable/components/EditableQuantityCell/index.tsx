import { ChangeEvent, KeyboardEvent, useEffect, useRef, useState } from 'react';

import { Typography } from '@mui/material';

import { StyledQuantityInput } from './styles';

interface EditableQuantityCellProps {
  value: number;
  isEditing?: boolean;
  onSave: (newValue: number) => void;
  onCancel: () => void;
}

const EditableQuantityCell = ({
  value,
  isEditing = false,
  onSave,
  onCancel,
}: EditableQuantityCellProps) => {
  const [inputValue, setInputValue] = useState<string>(value.toString());
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset input value when props change or when switching to edit mode
  useEffect(() => {
    setInputValue(value.toString());

    // Focus input when switching to edit mode
    if (isEditing && inputRef.current) {
      setTimeout(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      }, 0);
    }
  }, [value, isEditing]);

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    if (newValue === '' || /^\d+$/.test(newValue)) {
      setInputValue(newValue);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      const newValue = parseInt(inputValue.trim(), 10);
      if (!isNaN(newValue) && newValue >= 0) {
        onSave(newValue);
      } else {
        onCancel();
      }
    } else if (e.key === 'Escape') {
      setInputValue(value.toString());
      onCancel();
    }
  };

  const handleBlur = () => {
    setInputValue(value.toString());
    onCancel();
  };

  if (isEditing) {
    return (
      <StyledQuantityInput
        inputRef={inputRef}
        value={inputValue}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        inputProps={{
          min: 0,
          type: 'text',
          'aria-label': 'quantity',
        }}
        style={{ width: `${Math.max(4, inputValue.length)}ch` }}
      />
    );
  }

  return <Typography sx={{ fontSize: '14px' }}>{value}</Typography>;
};

export default EditableQuantityCell;
