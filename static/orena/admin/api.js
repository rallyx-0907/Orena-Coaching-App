/* The admin console's server boundary now lives in capabilities/admin-api.js, so the old console
   and the new UI's Admin (screens/admin) call the same functions (D-101 E: one Admin backend, one
   client). This file stays so the old console's imports keep working until the cutover. */
export * from '../capabilities/admin-api.js';
