import { Dialog, DialogActions, DialogContent, styled } from '@mui/material';

export const ModalContainer = styled(Dialog)({
  '& .MuiDialog-paper': {
    borderRadius: '10px',
    padding: '20px',
    width: '450px',
    backgroundColor: '#FFFFFF',
    boxSizing: 'border-box',
  },
  '& .MuiDialogTitle-root': {
    fontSize: '24px',
    fontWeight: '600',
    color: '#000000',
    textAlign: 'center',
    padding: '0 0 16px 0',
  },
});

export const ModalActions = styled(DialogActions)({
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  alignItems: 'stretch',
  width: '100%',
  gap: '16px',
  padding: '16px 0 0 0',
  margin: '0px',
  '& > *': {
    margin: '0 !important',
  },
});

export const ModalContent = styled(DialogContent)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'stretch',
  width: '100%',
  gap: '24px',
  padding: '0px',
  margin: '0px',
  overflowY: 'visible',
});

export const ModalDeleteActions = styled(DialogActions)({
  display: 'flex',
  flexDirection: 'row',
  gap: '16px',
});
