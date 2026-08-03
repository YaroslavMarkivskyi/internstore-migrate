export default function MockButtonCustomer({
  children,
  disabled,
  loading,
  variant,
  type,
  onClick,
}: {
  children: React.ReactNode;
  disabled?: boolean;
  loading?: boolean;
  variant?: 'contained' | 'outlined';
  type?: 'button' | 'submit' | 'reset';
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      data-testid={`button-${children?.toString().toLowerCase().replace(/\s+/g, '-')}`}
      data-variant={variant}
      data-loading={loading ? 'true' : 'false'}
      onClick={onClick}
    >
      {loading ? 'Loading...' : children}
    </button>
  );
}
