/* One in-flight request budget per room visit.

   Rapid navigation never used to cancel the room it left. A hashchange fires
   render() before whatever the previous room asked for has answered, so a
   long multi-room sweep at short dwell piles up requests nobody is waiting on
   any more - contending with the current room's own fetches for the same
   origin's connection budget. `#/language` surfaced this first because its
   read is the one room not wrapped in `Promise.allSettled`: any rejection,
   including one this contention causes, reaches the learner as a fully failed
   room instead of a degraded section the way `renderWorld` degrades.

   One controller per navigation. Starting the next aborts whatever the
   previous room was still waiting on, so a sweep never holds more than the
   current room's own requests open. */
let controller = new AbortController();

export function beginNavigation() {
  controller.abort();
  controller = new AbortController();
  return controller.signal;
}

export function navigationSignal() {
  return controller.signal;
}
