import React, { ChangeEvent, useRef, useState } from 'react';

import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import PhotoLibraryIcon from '@mui/icons-material/PhotoLibrary';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Slider,
  Stack,
  Typography,
} from '@mui/material';
import { styled } from '@mui/material/styles';

import { SERVER_URL } from '@services/http/api';

// API Configuration - Reuse shared SERVER_URL from api.ts
const API_BASE_URL = SERVER_URL;

const UploadBox = styled(Box)(({ theme }) => ({
  border: `2px dashed ${theme.palette.grey[300]}`,
  borderRadius: theme.spacing(1),
  padding: theme.spacing(3),
  textAlign: 'center',
  cursor: 'pointer',
  transition: 'border-color 0.3s ease',
  '&:hover': {
    borderColor: theme.palette.primary.main,
  },
}));

const PreviewImage = styled('img')({
  maxWidth: '100%',
  maxHeight: '200px',
  borderRadius: '8px',
  marginTop: '16px',
});

const GeneratedImage = styled('img')({
  maxWidth: '100%',
  maxHeight: '400px',
  borderRadius: '8px',
  objectFit: 'contain',
});

const ImageCountBox = styled(Box)(({ theme }) => ({
  padding: theme.spacing(2),
  borderRadius: theme.spacing(1),
  backgroundColor: theme.palette.grey[50],
  border: `1px solid ${theme.palette.grey[200]}`,
}));

interface AIImageGenerationModalProps {
  open: boolean;
  onClose: () => void;
  onImageGenerated: (imageFiles: File[]) => void;
  userId?: number;
}

const promptOptions = [
  'in a modern gym with dumbbells and workout equipment',
  'in a crossfit box with concrete walls and kettlebells',
  'on a rubber gym floor with a barbell in the background',
  'in a serene outdoor workout setting in nature',
  'in an urban cityscape showing a jogging path near a modern bridge or skyline',
];

const AIImageGenerationModal: React.FC<AIImageGenerationModalProps> = ({
  open,
  onClose,
  onImageGenerated,
  userId = 1,
}) => {
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [selectedPrompt, setSelectedPrompt] = useState<string>('');
  const [imageCount, setImageCount] = useState<number>(1);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string>('');
  const [generatedImageFiles, setGeneratedImageFiles] = useState<File[]>([]);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedImage(file);
      setError('');
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleImageCountChange = (
    _event: Event,
    newValue: number | number[]
  ) => {
    setImageCount(newValue as number);
  };

  const handleGenerate = async () => {
    if (!selectedImage) {
      setError('Please upload an image first');
      return;
    }

    if (!selectedPrompt) {
      setError('Please select a prompt');
      return;
    }

    setIsGenerating(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('user_id', userId.toString());
      formData.append('image', selectedImage);
      formData.append('prompt', selectedPrompt);
      formData.append('image_count', imageCount.toString());

      const response = await fetch(
        `${API_BASE_URL}admin/ai-image/generate-image/`,
        {
          method: 'POST',
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const blob = await response.blob();

      const generatedImageFile = new File([blob], 'generated-image.jpg', {
        type: 'image/jpeg',
      });

      setGeneratedImageFiles([generatedImageFile]);
      setShowConfirmation(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate image');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleConfirmImages = () => {
    if (generatedImageFiles.length > 0) {
      onImageGenerated(generatedImageFiles);
      handleClose();
    }
  };

  const handleDiscardImages = () => {
    setGeneratedImageFiles([]);
    setShowConfirmation(false);
  };

  const handleClose = () => {
    setSelectedImage(null);
    setSelectedPrompt('');
    setImageCount(1);
    setError('');
    setIsGenerating(false);
    setGeneratedImageFiles([]);
    setShowConfirmation(false);
    onClose();
  };

  return (
    <>
      {/* Main Generation Dialog */}
      <Dialog
        open={open && !showConfirmation}
        onClose={handleClose}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <AutoAwesomeIcon color="primary" />
            <Typography variant="h6">
              Generate Fitness Background with AI
            </Typography>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <Stack spacing={3} sx={{ mt: 1 }}>
            {/* Image Upload Section */}
            <Box>
              <Typography variant="subtitle1" gutterBottom>
                Upload Product Image
              </Typography>
              <UploadBox onClick={handleUploadClick}>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleImageUpload}
                  accept="image/*"
                  style={{ display: 'none' }}
                />
                {selectedImage ? (
                  <Box>
                    <Typography variant="body2" color="primary">
                      {selectedImage.name}
                    </Typography>
                    <PreviewImage
                      src={URL.createObjectURL(selectedImage)}
                      alt="Preview"
                    />
                  </Box>
                ) : (
                  <Box>
                    <CloudUploadIcon sx={{ fontSize: 48, color: 'grey.400' }} />
                    <Typography variant="body2" color="textSecondary">
                      Click to upload an image
                    </Typography>
                  </Box>
                )}
              </UploadBox>
            </Box>

            {/* Prompt Selection */}
            <Box>
              <Typography variant="subtitle1" gutterBottom>
                Select Fitness Background Style
              </Typography>
              <FormControl fullWidth>
                <InputLabel>Choose a fitness background</InputLabel>
                <Select
                  value={selectedPrompt}
                  label="Choose a fitness background"
                  onChange={e => setSelectedPrompt(e.target.value)}
                >
                  {promptOptions.map((prompt, index) => (
                    <MenuItem key={index} value={prompt}>
                      {prompt}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>

            {/* Image Count Selection */}
            <Box>
              <Typography variant="subtitle1" gutterBottom>
                Number of Image Variants
              </Typography>
              <ImageCountBox>
                <Stack direction="row" alignItems="center" spacing={2}>
                  <PhotoLibraryIcon color="primary" />
                  <Box sx={{ flex: 1 }}>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      gutterBottom
                    >
                      Generate {imageCount} variant{imageCount > 1 ? 's' : ''}{' '}
                      of your image
                    </Typography>
                    <Slider
                      value={imageCount}
                      onChange={handleImageCountChange}
                      min={1}
                      max={4}
                      step={1}
                      marks={[
                        { value: 1, label: '1' },
                        { value: 2, label: '2' },
                        { value: 3, label: '3' },
                        { value: 4, label: '4' },
                      ]}
                      valueLabelDisplay="auto"
                      sx={{ mt: 1 }}
                    />
                  </Box>
                  <Chip
                    label={`${imageCount} variant${imageCount > 1 ? 's' : ''}`}
                    color="primary"
                    size="small"
                  />
                </Stack>
              </ImageCountBox>
            </Box>

            {/* Error Display */}
            {error && (
              <Alert severity="error" onClose={() => setError('')}>
                {error}
              </Alert>
            )}

            {/* Loading State */}
            {isGenerating && (
              <Box sx={{ textAlign: 'center', py: 2 }}>
                <CircularProgress />
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Generating {imageCount} image variant
                  {imageCount > 1 ? 's' : ''}... This may take a few seconds.
                </Typography>
              </Box>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={isGenerating}>
            Cancel
          </Button>
          <Button
            onClick={handleGenerate}
            variant="contained"
            disabled={isGenerating || !selectedImage || !selectedPrompt}
            startIcon={
              isGenerating ? (
                <CircularProgress size={20} />
              ) : (
                <AutoAwesomeIcon />
              )
            }
          >
            {isGenerating
              ? 'Generating...'
              : `Generate ${imageCount} Image${imageCount > 1 ? 's' : ''}`}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirmation Dialog */}
      <Dialog
        open={showConfirmation}
        onClose={handleDiscardImages}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <AutoAwesomeIcon color="primary" />
            <Typography variant="h6">
              Review Generated Image{generatedImageFiles.length > 1 ? 's' : ''}
            </Typography>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography variant="body1" color="text.secondary">
              Here {generatedImageFiles.length > 1 ? 'are' : 'is'} your
              AI-generated image{generatedImageFiles.length > 1 ? 's' : ''}. Do
              you want to use{' '}
              {generatedImageFiles.length > 1 ? 'these images' : 'this image'}{' '}
              for your product?
            </Typography>

            {/* Display generated images */}
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                gap: 2,
              }}
            >
              {generatedImageFiles.map((imageFile, index) => (
                <Box key={index} sx={{ textAlign: 'center' }}>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: 'block', mb: 1 }}
                  >
                    Variant {index + 1}
                  </Typography>
                  <GeneratedImage
                    src={URL.createObjectURL(imageFile)}
                    alt={`Generated background variant ${index + 1}`}
                  />
                </Box>
              ))}
            </Box>

            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ textAlign: 'center' }}
            >
              Click "Discard" to try again, or "Confirm & Add Image
              {generatedImageFiles.length > 1 ? 's' : ''}" to add
              {generatedImageFiles.length > 1
                ? ' these images'
                : ' this image'}{' '}
              to your product.
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleDiscardImages}
            variant="outlined"
            startIcon={<CloseIcon />}
            color="error"
          >
            Discard
          </Button>
          <Button
            onClick={handleConfirmImages}
            variant="contained"
            startIcon={<CheckIcon />}
            color="primary"
          >
            Confirm & Add Image{generatedImageFiles.length > 1 ? 's' : ''}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default AIImageGenerationModal;
