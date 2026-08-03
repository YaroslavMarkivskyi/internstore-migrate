import React from 'react';

type Props = {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder: string;
  error?: string;
};

export const MockInputFieldCustomer = ({
  value,
  onChange,
  placeholder,
  error,
}: Props) => {
  return (
    <div data-testid={`input-field-${placeholder.toLowerCase()}`}>
      <input
        type="text"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        data-testid={`${placeholder.toLowerCase()}-input`}
      />
      {error && (
        <p data-testid={`${placeholder.toLowerCase()}-error`}>{error}</p>
      )}
    </div>
  );
};
