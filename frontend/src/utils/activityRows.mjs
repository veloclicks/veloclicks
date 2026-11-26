/** Transform the shared activity-list contract into the fields used by the table. */
export function toActivityRow(activity) {
  return {
    id: activity.id,
    name: activity.name,
    startDate: activity.start_date,
    dateTime: activity.start_date_local || activity.start_date,
    elapsedTime: Math.round((activity.elapsed_time || 0) / 60),
    distance: activity.distance || 0,
    avgSpeed: activity.average_speed || 0,
    elevationGain: activity.total_elevation_gain || 0,
    avgPower: activity.average_watts || 0,
    normalisedPower: activity.weighted_average_watts || 0,
  };
}

/** Keep one row per ID, with the more recent data source winning. */
export function mergeActivityRows(previous, incoming) {
  const byId = new Map(previous.map(row => [row.id, row]));
  for (const row of incoming) byId.set(row.id, row);
  return [...byId.values()].sort((left, right) =>
    right.startDate.localeCompare(left.startDate) || right.id - left.id
  );
}

/** Apply the API's selected-year range or default 180-day range to the snapshot. */
export function inActivityRange(row, years, now = new Date()) {
  if (!row.startDate) return false;
  if (!years.length) {
    const date = new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(row.startDate) ? row.startDate : row.startDate + 'Z');
    return date >= new Date(now.getTime() - 180 * 86400000) && date <= now;
  }
  const year = Number(row.startDate.slice(0, 4));
  return year >= Math.min(...years) && year <= Math.max(...years);
}
