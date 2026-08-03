import ButtonAdmin from '@components/UI/admin/ButtonAdmin';

export interface CancelButtonProps {
  onClick: () => void;
  isDisabled: boolean;
}

const CancelButton = ({ onClick, isDisabled }: CancelButtonProps) => {
  return (
    <>
      <ButtonAdmin
        variant="outlined"
        fullWidth={true}
        onClick={onClick}
        disabled={isDisabled}
      >
        Cancel
      </ButtonAdmin>
    </>
  );
};

export default CancelButton;
