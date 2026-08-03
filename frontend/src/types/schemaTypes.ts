import { z } from 'zod';

import { loginSchema } from '../schemas/login';

export type LoginDataType = z.infer<typeof loginSchema>;
