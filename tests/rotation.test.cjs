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

test('second and third suggestions wait for their required selections', () => {
  assert.deepEqual(R.recommend(games,[null,null,null],1),[]);
  assert.deepEqual(R.recommend(games,[id(botw),null,null],2),[]);
  assert.deepEqual(R.recommend(games,[null,id('Hi-Fi Rush'),null],2),[]);
  assert.ok(R.recommend(games,[id(botw),null,null],1).length > 0);
  assert.ok(R.recommend(games,[id(botw),id('Hi-Fi Rush'),null],2).length > 0);
});

test('changing the main game changes second-slot ranking and its explanation', () => {
  const withZelda = R.recommend(games,[id(botw),null,null],1,500);
  const withPersona = R.recommend(games,[id('Persona 5 Royal'),null,null],1,500);
  const score = (rows,name) => rows.find(row => row.game.name === name).score;
  assert.ok(score(withZelda,'Inscryption') > score(withPersona,'Inscryption'));
  assert.ok(score(withPersona,'Titanfall 2') > score(withZelda,'Titanfall 2'));
  assert.notDeepEqual(withZelda.map(x=>x.game.name),withPersona.map(x=>x.game.name));
  assert.match(withZelda[0].reason,/Breath of the Wild/);
  assert.match(withPersona[0].reason,/Persona 5 Royal/);
});

test('third slot evaluates mechanics of both selected games', () => {
  const bothAction = R.recommend(games,[id(botw),id('Hi-Fi Rush'),null],2,500);
  const withCards = R.recommend(games,[id(botw),id('Inscryption'),null],2,500);
  const changedFirst = R.recommend(games,[id('Persona 5 Royal'),id('Hi-Fi Rush'),null],2,500);
  const score = rows => rows.find(row=>row.game.name === 'Balatro').score;
  assert.ok(score(bothAction) > score(withCards));
  assert.ok(score(bothAction) > score(changedFirst));
  assert.match(bothAction[0].reason,/Breath of the Wild/);
  assert.match(bothAction[0].reason,/Hi-Fi Rush/);
  assert.ok(bothAction.every(row=>R.profile(row.game).kind === 'session'));
});

test('recommendations exclude duplicates, abandoned and unavailable games', () => {
  const sample = [
    named(botw),named('Hi-Fi Rush'),named('Balatro'),
    {...named('Slay the Spire'),list:'Q'},
    {...named('Rocket League'),steam:{comingSoon:true}},
    {...named('Hades II'),play:{status:'waiting'}},
    {...named('Returnal'),released:false},
  ];
  assert.deepEqual(R.recommend(sample,[id(botw),id('Hi-Fi Rush'),id('Balatro')],2,100),[]);
  assert.deepEqual(R.recommend(sample,[id(botw),id('Hi-Fi Rush'),null],2,100).map(x=>x.game.name),['Balatro']);
  assert.equal(R.isAvailable({...named('Slay the Spire'),list:'Q'}),true,'abandoned games remain manually selectable');
});

test('roguelike and sport completion times are never advertised as session lengths', () => {
  for (const name of ['Balatro','Slay the Spire','Hades','Hades II','Returnal','Risk of Rain 2','The Binding of Isaac: Rebirth','Rocket League','EA Sports FC 25','Brawlhalla','Guitar Hero']) {
    const p = R.profile(named(name));
    assert.equal(p.kind,'session',name);
    assert.equal(p.duration,null,name);
  }
  assert.equal(R.profile(named('Inscryption')).kind,'campaign');
  assert.equal(R.profile(named('Blue Prince')).kind,'long','long mystery does not become low-commitment simply because it has runs');
  assert.equal(R.profile(named('Portal')).tags.includes('shooter'),false,'metadata FPS label should not override the puzzle structure');
  assert.equal(R.profile(named('Warframe')).kind,'long','a continuing grind is not an independent-match recommendation');
});

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

test('browser export matches Node API and metadata gaps do not crash ranking', () => {
  const browser = {window:{}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../rotation.js'),'utf8'),browser);
  assert.equal(typeof browser.window.RotationEngine.recommend,'function');
  const unknown = {name:'Unknown'};
  assert.equal(R.profile(unknown).kind,'unknown');
  assert.deepEqual(R.recommend([unknown],[],0),[]);
  assert.equal(R.gameId({name:'Pokémon: Édition!'}),'pokemon-edition');
});
