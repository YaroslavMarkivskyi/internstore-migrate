import { FC } from 'react';

import { TextFieldProps, Typography } from '@mui/material';

import RichTextEditor from '../RichTextEditor';

import { ErrorWrapper, InputBase, InputWrapper, Label } from './styles';

export interface InputFieldProps
  extends Omit<TextFieldProps, 'variant' | 'helperText' | 'error'> {
  /** Whether to render input as Rich Text Editor or not */
  richEditing?: boolean;
  /** Error message to display */
  error?: string;
  /** Position to display error message. Use 'absolute' to render error message without disrupting layout. */
  errorPosition?: 'default' | 'absolute';
}

/** Basic Input Field for Admin Pages */
const InputFieldAdmin: FC<InputFieldProps> = ({
  error,
  required,
  label,
  errorPosition = 'default',
  richEditing = false,
  ...rest
}) => {
  const errorComponent = (
    <Typography color={'error'} fontSize={12}>
      {error}
    </Typography>
  );

  return (
    <InputWrapper>
      {!!label && (
        <Label>
          {label}
          {required && (
            <Typography
              component={'span'}
              color="error"
              fontWeight={500}
              fontSize={14}
            >
              {' '}
              *
            </Typography>
          )}
        </Label>
      )}
      {richEditing ? (
        <RichTextEditor value={rest.value} onChange={rest.onChange} />
      ) : (
        <InputBase {...rest} variant="outlined" />
      )}
      {!!error &&
        (errorPosition === 'absolute' ? (
          <ErrorWrapper>{errorComponent}</ErrorWrapper>
        ) : (
          errorComponent
        ))}
    </InputWrapper>
  );
};

export default InputFieldAdmin;
