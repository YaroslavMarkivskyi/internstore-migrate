import { forwardRef } from 'react';

import IOSSwitchStyled, { IOSSwitchProps } from './styles';

/**
 * Custom iOS style switch component
 *
 * This is a styled switch component that mimics the iOS switch appearance
 * with the brand accent color (#3D318E) when checked.
 */
const IOSSwitch = forwardRef<HTMLButtonElement, IOSSwitchProps>(
  (props, ref) => {
    return <IOSSwitchStyled ref={ref} {...props} />;
  }
);

export default IOSSwitch;
