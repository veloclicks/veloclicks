import { strict as assert } from 'node:assert';
import test from 'node:test';
import { inActivityRange, mergeActivityRows, toActivityRow } from '../src/utils/activityRows.mjs';

test('deduplicates snapshot and database rides with UTC ordering and ID ties', () => {
  const stale = toActivityRow({ id: 11, name: 'Cached', start_date: '2026-01-02T10:00:00' });
  const fresh = { ...stale, name: 'Updated', elapsedTime: 60 };
  const newer = toActivityRow({ id: 12, start_date: stale.startDate, start_date_local: '2026-01-02T06:00:00' });
  const oldest = toActivityRow({ id: 3, start_date: '2025-12-01T09:00:00' });
  assert.deepEqual(mergeActivityRows([stale, oldest], [fresh, newer]), [newer, fresh, oldest]);
});

test('filters snapshot rows by UTC year and the API default date range', () => {
  const now = new Date('2026-11-26T12:00:00Z');
  const ride = toActivityRow({ id: 1, start_date: '2026-06-01T12:00:00', start_date_local: '2026-06-01T13:00:00' });
  assert.equal(inActivityRange(ride, ['2026'], now), true);
  assert.equal(inActivityRange(ride, ['2025'], now), false);
  assert.equal(inActivityRange(ride, [], now), true);
  assert.equal(inActivityRange({ ...ride, startDate: '2026-01-01T12:00:00' }, [], now), false);
});
