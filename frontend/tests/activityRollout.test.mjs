import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isProgressiveActivityEnabled } from '../src/utils/activityRollout.mjs';

test('only production hosts activate by default and explicit overrides win', () => {
  assert.equal(isProgressiveActivityEnabled('www.veloclicks.com'), true);
  assert.equal(isProgressiveActivityEnabled('veloclicks-prod.vercel.app'), true);
  assert.equal(isProgressiveActivityEnabled('veloclicks-demo.vercel.app'), false);
  assert.equal(isProgressiveActivityEnabled('localhost'), false);
  assert.equal(isProgressiveActivityEnabled('www.veloclicks.com', '0'), false);
  assert.equal(isProgressiveActivityEnabled('localhost', '1'), true);
});
