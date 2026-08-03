import { InputBase, styled } from '@mui/material';

export const StyledQuantityInput = styled(InputBase)({
  backgroundColor: '#FAFAFA',
  border: '1px solid #E0E0E0',
  borderRadius: '5px',

  '& .MuiInputBase-input': {
    textAlign: 'center',
    fontSize: '14px',
    padding: '5px 0px',
  },
});
