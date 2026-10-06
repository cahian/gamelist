const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const R = require('../rotation.js');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(require.resolve('../data.js'),'utf8') + ';globalThis.catalog = GAMES;',context);
const games = context.catalog;
const named = name => {
  const game = games.find(g => g.name === name);
  assert.ok(game, `missing catalog fixture: ${name}`);
  return game;
};
const id = name => R.gameId(named(name));
const botw = 'The Legend of Zelda: Breath of the Wild';

test('normalization and saved state recover safely from malformed, stale and duplicate values', () => {
  const a = id(botw), b = id('Hi-Fi Rush');
  assert.deepEqual(R.normalizeSlots([a,a,b,'extra'],games),[a,null,b]);
  assert.deepEqual(R.normalizeSlots(['missing',42,b],games),[null,null,b]);
  assert.deepEqual(R.normalizeSlots({0:a},games),[null,null,null]);
  let value = '{broken';
  const storage = {getItem:()=>value,setItem:(key,next)=>{assert.equal(key,R.STORAGE_KEY);value=next;}};
  assert.deepEqual(R.readSlots(storage,games),[null,null,null]);
  assert.equal(R.saveSlots(storage,[a,b,null]),true);
  assert.deepEqual(R.readSlots(storage,games),[a,b,null]);
  value = JSON.stringify({version:1,slots:[a,'removed-from-catalog',b]});
  assert.deepEqual(R.readSlots(storage,games),[a,null,b]);
  value = JSON.stringify({version:99,slots:[a,b,null]});
  assert.deepEqual(R.readSlots(storage,games),[null,null,null]);
  const denied = {getItem:()=>{throw new Error('blocked');},setItem:()=>{throw new Error('quota');}};
  assert.deepEqual(R.readSlots(denied,games),[null,null,null]);
  assert.equal(R.saveSlots(denied,[a,b,null]),false);
});

test('browser export supports manual rotation and stable game IDs', () => {
  const browser = {window:{}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../rotation.js'),'utf8'),browser);
  const slots = browser.window.RotationEngine.normalizeSlots([id(botw),id('Hi-Fi Rush'),null],games);
  assert.deepEqual(Array.from(slots),[id(botw),id('Hi-Fi Rush'),null]);
  assert.equal(R.gameId({name:'Pokémon: Édition!'}),'pokemon-edition');
});
