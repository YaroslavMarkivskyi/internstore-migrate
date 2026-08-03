import { ChangeEvent, FC, useEffect, useRef, useState } from 'react';

import { useNavigate } from 'react-router';

import axios from 'axios';

import { zodResolver } from '@hookform/resolvers/zod';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ImageOutlinedIcon from '@mui/icons-material/ImageOutlined';
import { InputAdornment, Radio, Stack, Typography } from '@mui/material';
import { Controller, useForm } from 'react-hook-form';

import CategorySelect from '@components/CategorySelect';
import { getImages, getProduct } from '@services/http/admin/products';
import { handleFormErrors } from '@utils/handleFormErrors';

import ButtonAdmin from '../UI/admin/ButtonAdmin';
import InputFieldAdmin from '../UI/admin/InputFieldAdmin';

import { IProductImage } from '../../types/products/interfaces';
import showToast from '../../utils/showToast';

import AIImageGenerationModal from './components/AIImageGenerationModal';
import ImageCell from './components/ImageCell';
import ImagePreview from './components/ImagePreview';
import {
  MAX_IMAGES,
  ProductFormDataInput,
  ProductFormDataOutput,
  productSchema,
} from './schema';
import {
  ButtonsContainer,
  FormColumnContainer,
  FormColumnsWrapper,
  FormContainer,
  FormWrapper,
  PathContainer,
  PathIcon,
  PathTextDetails,
  PathTextParent,
  UploadImageButton,
  UploadImageError,
  UploadImageWrapper,
} from './styles';

interface ProductFormProps {
  /** Function to be called when form is submitted. Errors are handled internally */
  onSubmit: (product: ProductFormDataOutput) => Promise<void>;
  /** ID of product to load initial data from */
  productId?: string;
  /** Is product duplicating */
  isDuplicate?: boolean;
}

const ProductForm: FC<ProductFormProps> = ({
  onSubmit,
  productId,
  isDuplicate,
}) => {
  const [_isLoadingData, setIsLoadingData] = useState(false);

  const {
    handleSubmit,
    control,
    setValue,
    watch,
    setError,
    reset,
    formState: { errors, isValid, isLoading, isSubmitting },
  } = useForm<ProductFormDataInput, object, ProductFormDataOutput>({
    resolver: zodResolver(productSchema),
    mode: 'onChange',
    defaultValues: {} as ProductFormDataInput,
  });

  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadedImages = watch('photos');
  const imagesToDelete = watch('photosToDelete');

  const productName = watch('name');

  const navigate = useNavigate();

  const [isAIImageGenerationModalOpen, setIsAIImageGenerationModalOpen] =
    useState(false);

  // Load product data when component mounts or productId changes
  useEffect(() => {
    const loadProductData = async () => {
      if (productId) {
        setIsLoadingData(true);
        try {
          const productData = await getProduct(productId);
          const imagesData = await getImages(productId);

          const formData: ProductFormDataInput = {
            name: isDuplicate ? `[COPY] ${productData.name}` : productData.name,
            description: productData.description,
            minTemperature: productData.minTemperature,
            maxTemperature: productData.maxTemperature,
            category: productData.category?.id || '',
            price: productData.price,
            photos: imagesData,
          };

          // Reset form with loaded data
          reset(formData);
          console.log('Product data loaded successfully:', formData);
        } catch (error) {
          console.error('Error loading product data:', error);
          setError('root', {
            type: 'server',
            message: 'Error loading product data.',
          });
        } finally {
          setIsLoadingData(false);
        }
      }
    };

    loadProductData();
  }, [productId, isDuplicate, reset, setError]);

  const handleUploadImageClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const currentLength = uploadedImages ? uploadedImages.length : 0;
    if (!event.target.files || currentLength >= MAX_IMAGES) return;

    const amountToAdd = currentLength === 0 ? MAX_IMAGES : currentLength;
    const newFiles = [
      ...(uploadedImages || []),
      ...Array.from(event.target.files).slice(0, amountToAdd),
    ];

    setValue('photos', newFiles, { shouldValidate: true });

    // File input not detecting the same file.
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

    return newFiles;
  };

  const handleDeleteImage = (index: number) => {
    if (!uploadedImages) return;

    const imageToDelete = uploadedImages[index];
    const newImages = uploadedImages.filter(image => image !== imageToDelete);
    setValue('photos', newImages, { shouldValidate: true });

    if (!(imageToDelete instanceof File)) {
      const oldImagesToDelete = imagesToDelete ? imagesToDelete : [];
      setValue('photosToDelete', [...oldImagesToDelete, imageToDelete]);
    }
  };

  const handleAIImageGenerated = (generatedImages: File[]) => {
    const currentImages = uploadedImages || [];

    // Check if adding all images would exceed the limit
    if (currentImages.length + generatedImages.length > MAX_IMAGES) {
      showToast({
        message: 'Adding these images would exceed the maximum limit',
        type: 'error',
      });
      return;
    }

    const newImages = [...currentImages, ...generatedImages];
    setValue('photos', newImages, { shouldValidate: true });
    showToast({
      message: `${generatedImages.length} AI image${generatedImages.length > 1 ? 's' : ''} generated successfully!`,
      type: 'success',
    });
  };

  const handleOpenAIModal = () => {
    setIsAIImageGenerationModalOpen(true);
  };

  const handleCloseAIModal = () => {
    setIsAIImageGenerationModalOpen(false);
  };

  const convertPhotoToFile = async (
    photo: IProductImage | File
  ): Promise<File> => {
    if (photo instanceof File) return photo;

    const response = await axios.get(photo.image, { responseType: 'blob' });
    const blob = response.data;
    return new File([blob], `${photo.id}.jpg`, { type: blob.type });
  };

  const preparePayload = async (
    data: ProductFormDataOutput
  ): Promise<ProductFormDataOutput> => {
    if (!isDuplicate) return data;

    const photos = await Promise.all(
      (data.photos ?? []).map(convertPhotoToFile)
    );
    return { ...data, photos };
  };

  const onSubmitWrapper = async (data: ProductFormDataOutput) => {
    try {
      const payload = await preparePayload(data);
      await onSubmit(payload);

      showToast({ message: 'Saved successfully', type: 'success' });
      navigate('/admin/products');
    } catch (error: unknown) {
      handleFormErrors(error, setError);
    }
  };

  const onDiscard = () => {
    navigate(-1);
  };

  return (
    <FormWrapper>
      <PathContainer>
        <PathTextParent>Products</PathTextParent>
        <PathIcon />
        <PathTextDetails>
          {productId ? productName : 'Add a product'}
        </PathTextDetails>
      </PathContainer>
      <FormContainer onSubmit={handleSubmit(onSubmitWrapper)}>
        <FormColumnsWrapper>
          <FormColumnContainer>
            <ImagePreview
              imageUrl={
                uploadedImages?.[0]
                  ? uploadedImages[0] instanceof File
                    ? URL.createObjectURL(uploadedImages[0])
                    : uploadedImages[0].image
                  : undefined
              }
            />
            <Stack direction="row" justifyContent="space-between">
              {uploadedImages &&
                [...uploadedImages].map((file, index) => (
                  <ImageCell
                    key={index}
                    imageUrl={
                      file instanceof File
                        ? URL.createObjectURL(file)
                        : file.image
                    }
                    onDelete={() => handleDeleteImage(index)}
                  />
                ))}
              {[...Array(MAX_IMAGES - (uploadedImages?.length ?? 0))].map(
                (_, index) => (
                  <ImageCell key={index} />
                )
              )}
            </Stack>
            <UploadImageWrapper>
              <Stack direction="row" spacing={1}>
                <UploadImageButton
                  variant="contained"
                  fullWidth
                  startIcon={<ImageOutlinedIcon />}
                  disableElevation
                  onClick={handleUploadImageClick}
                  disabled={uploadedImages?.length === MAX_IMAGES}
                >
                  Upload Image
                </UploadImageButton>
                <UploadImageButton
                  variant="outlined"
                  fullWidth
                  startIcon={<AutoAwesomeIcon />}
                  disableElevation
                  onClick={handleOpenAIModal}
                  disabled={uploadedImages?.length === MAX_IMAGES}
                >
                  Generate background with AI
                </UploadImageButton>
              </Stack>
              <Controller
                name="photos"
                defaultValue={[]}
                control={control}
                render={({ field: { onChange, ref } }) => (
                  <input
                    type="file"
                    accept="image/png, image/jpg, image/jpeg"
                    hidden
                    multiple
                    ref={e => {
                      ref(e);
                      fileInputRef.current = e;
                    }}
                    onChange={event => onChange(handleFileChange(event))}
                  />
                )}
              />
              <UploadImageError color={'error'} fontSize={12}>
                {errors.photos?.message}
              </UploadImageError>
            </UploadImageWrapper>
          </FormColumnContainer>
          <FormColumnContainer>
            <Controller
              name="name"
              control={control}
              defaultValue={''}
              render={({ field }) => (
                <InputFieldAdmin
                  {...field}
                  required
                  label="Product Name"
                  errorPosition="absolute"
                  fullWidth
                  error={errors.name?.message}
                />
              )}
            />
            <Controller
              name="category"
              control={control}
              defaultValue={''}
              render={({ field }) => (
                <CategorySelect
                  {...field}
                  required
                  label="Category"
                  name="category"
                  errorPosition="absolute"
                  fullWidth
                  error={errors.category?.message}
                  endComponent={<Radio size="small" />}
                />
              )}
            />
            <Controller
              name="price"
              defaultValue={''}
              control={control}
              render={({ field }) => (
                <InputFieldAdmin
                  {...field}
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start">$</InputAdornment>
                      ),
                    },
                  }}
                  required
                  label="Price"
                  errorPosition="absolute"
                  fullWidth
                  error={errors.price?.message}
                />
              )}
            />
            <Stack direction="row" justifyContent="space-between" spacing={2.5}>
              <Controller
                name="minTemperature"
                defaultValue={''}
                control={control}
                render={({ field }) => (
                  <InputFieldAdmin
                    {...field}
                    slotProps={{ htmlInput: { type: 'number' } }}
                    label="Min Temperature °C"
                    errorPosition="absolute"
                    fullWidth
                    error={errors.minTemperature?.message}
                  />
                )}
              />
              <Controller
                name="maxTemperature"
                defaultValue={''}
                control={control}
                render={({ field }) => (
                  <InputFieldAdmin
                    {...field}
                    slotProps={{ htmlInput: { type: 'number' } }}
                    label="Max Temperature °C"
                    errorPosition="absolute"
                    fullWidth
                    error={errors.maxTemperature?.message}
                  />
                )}
              />
            </Stack>
          </FormColumnContainer>
          <FormColumnContainer>
            <Controller
              name="description"
              control={control}
              defaultValue={''}
              render={({ field }) => (
                <InputFieldAdmin
                  {...field}
                  label="Description"
                  errorPosition="absolute"
                  richEditing
                  error={errors.description?.message}
                />
              )}
            />
          </FormColumnContainer>
        </FormColumnsWrapper>
        <FormColumnsWrapper>
          <FormColumnContainer></FormColumnContainer>
          <FormColumnContainer>
            <Typography
              color="error"
              fontSize={12}
              textAlign="center"
              my={'auto'}
            >
              {errors.root?.message}
            </Typography>
          </FormColumnContainer>
          <FormColumnContainer>
            <ButtonsContainer>
              <ButtonAdmin fullWidth variant="outlined" onClick={onDiscard}>
                Discard
              </ButtonAdmin>
              <ButtonAdmin
                fullWidth
                variant="contained"
                disabled={!isValid || isLoading}
                type="submit"
                loading={isSubmitting}
                loadingPosition="center"
              >
                {isSubmitting ? '' : 'Save'}
              </ButtonAdmin>
            </ButtonsContainer>
          </FormColumnContainer>
        </FormColumnsWrapper>
      </FormContainer>
      <AIImageGenerationModal
        open={isAIImageGenerationModalOpen}
        onClose={handleCloseAIModal}
        onImageGenerated={handleAIImageGenerated}
        userId={1}
      />
    </FormWrapper>
  );
};

export default ProductForm;
