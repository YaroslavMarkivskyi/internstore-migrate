import React from 'react';

type Props = {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder: string;
  error?: string;
  name: string;
};

export default function MockInputFieldAdmin({
  value,
  onChange,
  placeholder,
  error,
  name,
}: Props) {
  return (
    <div data-testid={`input-field-${name.toLowerCase()}`}>
      <input
        type="text"
        value={value}
        name={name}
        onChange={onChange}
        placeholder={placeholder}
        data-testid={`${name.toLowerCase()}-input`}
      />
      {error && <p data-testid={`${name.toLowerCase()}-error`}>{error}</p>}
    </div>
  );
}
