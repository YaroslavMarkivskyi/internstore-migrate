import ButtonAdmin from '@components/UI/admin/ButtonAdmin';

export interface SaveButtonProps {
  onClick: () => void;
  isDisabled: boolean;
}

const SaveButton = ({ onClick, isDisabled }: SaveButtonProps) => {
  return (
    <>
      <ButtonAdmin
        variant="contained"
        fullWidth={true}
        onClick={onClick}
        disabled={isDisabled}
      >
        Save
      </ButtonAdmin>
    </>
  );
};

export default SaveButton;
