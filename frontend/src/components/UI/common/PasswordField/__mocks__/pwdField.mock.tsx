export default function MockPasswordField({
  value,
  onChange,
  placeholder,
  error,
}: {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder: string;
  error?: string;
}) {
  return (
    <div data-testid="password-field">
      <input
        type="password"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        data-testid="password-input"
      />
      {error && <p data-testid="password-error">{error}</p>}
    </div>
  );
}
