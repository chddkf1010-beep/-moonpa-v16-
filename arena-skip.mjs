/** Complete the current live group battle using its *existing* deterministic rules.
 * This changes only presentation timing; it does not choose a winner or mutate
 * game economy/ownership. The normal result confirmation remains authoritative.
 */
export function finishGroupBattleNow(game, engine) {
  if (!game || game.finished || (game.mode !== 8 && game.mode !== 10)) return false;
  while (!game.finished) engine.tick(game);
  return true;
}
