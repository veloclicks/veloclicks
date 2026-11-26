const productionHosts = new Set(['www.veloclicks.com', 'veloclicks-prod.vercel.app']);

export function isProductionActivityHost(hostname) {
  return productionHosts.has(hostname);
}

export function isProgressiveActivityEnabled(hostname, override) {
  if (override === '0') return false;
  return override === '1' || isProductionActivityHost(hostname);
}
