import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import { Stack } from '@mui/material';

import { AddDestinationStockIcon, MoveToStockText } from '../../styles';

export type AddDestinationButtonProps = {
  onClick: () => void;
};

const AddDestinationButton = ({ onClick }: AddDestinationButtonProps) => {
  return (
    <Stack
      direction="row"
      justifyContent="center"
      sx={{ marginTop: '15px', cursor: 'pointer' }}
      onClick={onClick}
    >
      <MoveToStockText>Add a stock</MoveToStockText>
      <AddDestinationStockIcon>
        <AddCircleOutlineIcon />
      </AddDestinationStockIcon>
    </Stack>
  );
};

export default AddDestinationButton;
