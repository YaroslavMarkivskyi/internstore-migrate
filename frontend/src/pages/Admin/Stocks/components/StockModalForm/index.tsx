import { useEffect, useRef, useState } from 'react';

import { useNavigate } from 'react-router';

import { zodResolver } from '@hookform/resolvers/zod';
import { DialogTitle, Typography } from '@mui/material';
import { useForm } from 'react-hook-form';

import { stockSchema } from '@/schemas/stocks';
import ButtonAdmin from '@components/UI/admin/ButtonAdmin';
import InputFieldAdmin from '@components/UI/admin/InputFieldAdmin';
import { stockService } from '@services/http';
import { handleFormErrors } from '@utils/handleFormErrors';
import showToast from '@utils/showToast';

import { IStock } from '../../../../../types/stocks/interfaces';
import { useModal } from '../../hooks/ModalStockContext';

import {
  ModalActions,
  ModalContainer,
  ModalContent,
  ModalDeleteActions,
} from './styles';

interface Props {
  refetchStocks: () => Promise<void>;
  isProducts: boolean;
}

export default function StockModalForm({ refetchStocks, isProducts }: Props) {
  const { isOpen, mode, initialData, header, closeModal, openModal } =
    useModal();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);

  const toastAnchorEl = useRef(null);

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<IStock>({
    resolver: zodResolver(stockSchema),
    defaultValues: { name: '' },
  });

  const isEdit = mode === 'edit';
  const isAdd = mode === 'add';
  const isDelete = mode === 'delete';
  const isFormMode = isAdd || isEdit;

  useEffect(() => {
    if (isFormMode) {
      reset({ name: initialData?.name || '' });
    }
  }, [initialData, isFormMode, reset]);

  useEffect(() => {
    if (!isOpen) {
      reset();
    }
  }, [isOpen, reset]);

  const onSubmit = async (data: IStock) => {
    try {
      let response: IStock | undefined;

      setIsLoading(true);

      if (isAdd) {
        response = await stockService.createStock(data);
      } else if (isEdit && initialData?.id) {
        response = await stockService.updateStock(initialData.id, data);
      }

      showToast({
        message: 'Saved successfully',
        type: 'success',
        anchorEl: toastAnchorEl.current,
        autoClose: 1000,
        style: { boxShadow: 'none' },
        onClose: async () => {
          if (response) {
            await refetchStocks();
            navigate(`/admin/stocks/${response.id}`);
            reset();
            closeModal();
          }
          setIsLoading(false);
        },
      });
    } catch (error) {
      handleFormErrors(error, setError);
      setIsLoading(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!initialData?.id) {
      return;
    }
    setIsLoading(true);
    try {
      await stockService.deleteStock(initialData.id);
      showToast({
        message: 'Deleted successfully',
        type: 'success',
        anchorEl: toastAnchorEl.current,
        autoClose: 1000,
        style: { boxShadow: 'none' },
        onClose: async () => {
          await refetchStocks();
          navigate('/admin/stocks');
          reset();
          closeModal();
          setIsLoading(false);
        },
      });
    } catch {
      showToast({
        message: 'Error deleting the stock',
        type: 'error',
      });
      setIsLoading(false);
    }
  };

  const handleDeleteClick = () => {
    if (initialData?.id) {
      openModal({ mode: 'delete', initialData });
    }
  };

  const renderForm = () => (
    <form onSubmit={handleSubmit(onSubmit)} style={{ width: '100%' }}>
      <InputFieldAdmin
        placeholder="name"
        required
        {...register('name')}
        error={errors.name?.message}
      />

      <ModalActions ref={toastAnchorEl}>
        <ButtonAdmin
          variant="contained"
          type="submit"
          fullWidth
          disabled={!!errors.name || isLoading}
        >
          Save
        </ButtonAdmin>
        <ButtonAdmin
          variant="outlined"
          onClick={closeModal}
          disabled={isLoading}
          fullWidth
        >
          Cancel
        </ButtonAdmin>
        {isEdit && (
          <ButtonAdmin
            variant="text"
            color="error"
            onClick={handleDeleteClick}
            fullWidth
            disabled={isProducts || isLoading}
          >
            Delete the stock
          </ButtonAdmin>
        )}
      </ModalActions>
    </form>
  );

  const renderDeleteConfirmation = () => (
    <>
      <Typography variant="body1" sx={{ textAlign: 'center' }}>
        Are you sure you would like to delete "{initialData?.name}"?
      </Typography>
      <ModalDeleteActions ref={toastAnchorEl}>
        <ButtonAdmin
          variant="outlined"
          onClick={closeModal}
          disabled={isLoading}
          fullWidth
        >
          No
        </ButtonAdmin>
        <ButtonAdmin
          variant="contained"
          color="error"
          onClick={handleDeleteConfirm}
          fullWidth
          disabled={isLoading}
        >
          Yes
        </ButtonAdmin>
      </ModalDeleteActions>
    </>
  );

  return (
    <ModalContainer open={isOpen} onClose={closeModal}>
      <DialogTitle>{header}</DialogTitle>
      <ModalContent>
        {isFormMode && renderForm()}
        {isDelete && initialData && renderDeleteConfirmation()}
      </ModalContent>
    </ModalContainer>
  );
}
