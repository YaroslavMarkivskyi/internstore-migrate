import { useEffect, useRef, useState } from 'react';

import CheckIcon from '@mui/icons-material/Check';
import { Box, IconButton, TextField } from '@mui/material';

import { InputContainer } from './styles';

interface CategoriesInputProps {
  initialValue?: string;
  placeholder?: string;
  maxLength?: number;
  position?: {
    left?: string;
    right?: string;
    top?: string;
  };
  onSubmit: (value: string) => Promise<void>;
  onCancel: () => void;
}

const CategoriesInput = ({
  initialValue = '',
  placeholder = 'Enter category name',
  maxLength = 15,
  position,
  onSubmit,
  onCancel,
}: CategoriesInputProps) => {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Focus the input when it mounts
  useEffect(() => {
    setTimeout(() => {
      inputRef.current?.focus();
    }, 100);
  }, []);

  // Handle clicks outside the component
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node) &&
        !isSubmitting
      ) {
        onCancel();
      }
    };

    // Add the event listener
    document.addEventListener('mousedown', handleClickOutside);

    // Clean up
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isSubmitting, onCancel]);

  const handleSubmit = async () => {
    if (!value.trim()) {
      setError('Category name cannot be empty');
      return;
    }

    try {
      setIsSubmitting(true);
      await onSubmit(value);
    } catch (error: any) {
      console.error('Error submitting category:', error);
      if (error.response?.data?.name) {
        setError(error.response.data.name[0]);
      } else {
        setError('Failed to save category. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter') {
      handleSubmit();
    } else if (e.key === 'Escape') {
      onCancel();
    }
  };

  return (
    <InputContainer ref={containerRef} sx={position}>
      <Box
        sx={{
          display: 'flex',
          width: '100%',
          padding: '3px',
          alignItems: 'center',
        }}
      >
        <TextField
          inputRef={inputRef}
          placeholder={placeholder}
          size="small"
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          error={!!error}
          helperText={error}
          disabled={isSubmitting}
          autoFocus
          inputProps={{
            maxLength,
            style: {
              fontSize: '16px',
              fontFamily: '"Noto Sans", sans-serif',
            },
          }}
          sx={{
            flexGrow: 1,
            mr: 1,
            '& .MuiOutlinedInput-root': {
              borderRadius: '6px',
              '& fieldset': {
                borderColor: '#E0E0E0',
                borderWidth: '1px',
              },
              '&:hover fieldset': {
                borderColor: '#E0E0E0',
              },
              '&.Mui-focused fieldset': {
                borderColor: '#E0E0E0',
                borderWidth: '1px',
              },
            },
          }}
          FormHelperTextProps={{
            sx: {
              position: 'absolute',
              bottom: '-20px',
              margin: 0,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '100%',
            },
          }}
        />
        <IconButton
          size="small"
          onClick={handleSubmit}
          disabled={isSubmitting || !value.trim()}
          sx={{
            backgroundColor: '#3D318E',
            color: 'white',
            width: '44px',
            height: '44px',
            borderRadius: '0',
            minWidth: '44px',
            flexShrink: 0,
            '&:hover': {
              backgroundColor: '#332679',
            },
            '&.Mui-disabled': {
              backgroundColor: '#E3E3EB',
              color: '#8B8B8B',
            },
            padding: '0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <CheckIcon fontSize="small" />
        </IconButton>
      </Box>
    </InputContainer>
  );
};

export default CategoriesInput;
