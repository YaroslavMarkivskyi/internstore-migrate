import { Dialog, styled } from '@mui/material';

export const DeleteConfirmationDialog = styled(Dialog)(({ theme }) => ({
  '& .MuiDialog-paper': {
    borderRadius: '5px',
    padding: theme.spacing(2),
    boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.1)',
    width: '450px',
    fontSize: '16px',
    fontWeight: 500,
    fontFamily: 'Noto Sans',
    display: 'flex',
    flexDirection: 'column',
  },
  '& .MuiDialogTitle-root': {
    fontSize: '16px',
    fontWeight: 500,
    fontFamily: 'Noto Sans',
    textAlign: 'center',
    padding: '30px 0 0 0',
  },
  '& .MuiDialogContent-root': {
    display: 'flex',
    fontSize: '14px',
    fontWeight: 400,
    fontFamily: 'Noto Sans',
    padding: theme.spacing(2),
  },
  '& .MuiDialogActions-root': {
    padding: theme.spacing(2),
    justifyContent: 'flex-end',
  },
}));
