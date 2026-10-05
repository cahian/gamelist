const {test} = require('node:test');
const assert = require('node:assert/strict');
const {escapeHtml, safeUrl, compare} = require('../app.js');
test('provider text cannot inject HTML into titles or attributes', () => {
  assert.equal(escapeHtml('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
  assert.equal(safeUrl('javascript:alert(1)'), '');
  assert.equal(safeUrl('https://www.protondb.com/app/1'), 'https://www.protondb.com/app/1');
});
test('games without completion times remain last in both sort directions', () => {
  const values = [null,40,10,null,2];
  assert.deepEqual([...values].sort((a,b) => compare(a,b,true)), [2,10,40,null,null]);
  assert.deepEqual([...values].sort((a,b) => compare(a,b,false)), [40,10,2,null,null]);
});
