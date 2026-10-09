/* The one way every "+ Import" control opens the Import flow (D-167): Discover's header and its Imported call to
   action, Today's featured card and My Library's header all call this, so they cannot drift apart. The sheet
   itself is loaded on first use (screens/import/sheet.js). */
export function openImportFlow(ctx, options) {
  return import('./sheet.js')
    .then((module) => module.openImport(ctx, options))
    .catch((error) => console.error('[Orena] Import is not available yet', error));
}
