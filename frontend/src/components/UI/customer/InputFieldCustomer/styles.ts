import { styled } from '@mui/material/styles';

import colors from '../../../../constants/colors';
import InputFieldAdmin from '../../admin/InputFieldAdmin';

export const InputFieldBase = styled(InputFieldAdmin)({
  '& .MuiOutlinedInput-root': {
    borderRadius: '5px',
    background: colors.secondary.background,
    border: `1px solid ${colors.border}`,
    fontFamily: 'Noto Sans',
    fontSize: '14px',
  },
});
