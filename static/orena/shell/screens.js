/* The screens of the new learner UI that are built, by the folder name a route names in
   shell/routes.js (`screen`). A route whose screen is not listed here renders the design's Coming
   soon screen. Each loader is a dynamic import so a learner downloads a room only when they enter
   it; scripts/validate_browser_esm_graph.mjs walks every screen listed here. */
export const SCREENS = Object.freeze({
  coming: () => import('../screens/coming/screen.js'),
});
