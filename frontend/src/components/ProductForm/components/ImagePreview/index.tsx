import { FC } from 'react';

import { Image, ImageContainer, PlaceholderIcon } from './styles';

interface ImagePreviewProps {
  imageUrl?: string;
}

const ImagePreview: FC<ImagePreviewProps> = ({ imageUrl }) => {
  return (
    <ImageContainer>
      {imageUrl ? <Image src={imageUrl} alt="preview" /> : <PlaceholderIcon />}
    </ImageContainer>
  );
};

export default ImagePreview;
