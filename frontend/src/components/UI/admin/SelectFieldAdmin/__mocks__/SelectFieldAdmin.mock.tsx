import React from 'react';

import { SelectItem } from '@components/UI/admin/SelectFieldAdmin';

type Props = {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  label: string;
  error?: string;
  name: string;
  multiple: boolean;
  options: SelectItem[];
};

export default function MockSelectFieldAdmin({
  value,
  onChange,
  label,
  error,
  name,
  options,
  multiple,
}: Props) {
  return (
    <div data-testid={`input-field-${name.toLowerCase()}`}>
      <label htmlFor={name}>{label}</label>
      <select
        value={value}
        onChange={onChange}
        name={name}
        multiple={multiple}
        data-testid={`${name.toLowerCase()}-input`}
      >
        {options.map(option => (
          <option value={option.value} key={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && <p data-testid={`${name.toLowerCase()}-error`}>{error}</p>}
    </div>
  );
}
