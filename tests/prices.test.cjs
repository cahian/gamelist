const {test} = require('node:test');
const assert = require('node:assert/strict');
const {state,render,applySnapshot} = require('../prices.js');
const game = (price, source = {}) => ({steam:{appid:620}, price,
  sources:{steamPrice:{status:'ok',updatedAt:new Date().toISOString(),...source}}});
const offer = {country:'BR',currency:'BRL',status:'available',initial:10000,final:5000,discountPercent:50,isFree:false};
test('Brazilian discounts keep cents, price and original offer separate', () => {
  const result = state(game(offer));
  assert.equal(result.value,5000); assert.equal(result.discount,50);
  assert.equal(result.initial,10000); assert.equal(result.free,false);
  assert.match(result.label,/50,00/); assert.match(render(game(offer)),/−50%/);
});
test('unavailable, missing and foreign prices are never shown as free', () => {
  for (const price of [null,{...offer,status:'unavailable',final:null},{...offer,currency:'USD'}]) {
    const result = state(game(price)); assert.equal(result.value,null); assert.equal(result.free,false);
  }
  const result = state(game({...offer,status:'free',isFree:true,initial:0,final:0,discountPercent:0}));
  assert.equal(result.label,'Gratuito'); assert.equal(result.value,0); assert.equal(result.free,true);
});
test('failed or old quotes retain amount with an explicit previous-data warning', () => {
  for (const source of [{status:'stale'},{updatedAt:'2020-01-01T00:00:00Z'}]) {
    assert.equal(state(game(offer,source)).stale,true);
    assert.match(render(game(offer,source)),/Dado anterior/);
  }
  assert.equal(state(game(null,{status:'error',updatedAt:null})).label,'Consulta indisponível');
});
const snapshot = source => ({version:1,country:'BR',currency:'BRL',generatedAt:new Date().toISOString(),prices:{620:source}});
test('fresh snapshots merge by Steam edition without changing rotation metadata', () => {
  const target = {...game({...offer,appid:620}),name:'Portal 2',list:'B'};
  const updatedAt = new Date(Date.now()+1000).toISOString();
  assert.equal(applySnapshot([target],snapshot({status:'ok',updatedAt,data:{...offer,appid:620,final:4000,discountPercent:60}})).applied,1);
  assert.equal(target.price.final,4000); assert.equal(target.name,'Portal 2'); assert.equal(target.list,'B');
  assert.equal(target.sources.steamPrice.updatedAt,updatedAt);
});
test('older, foreign and mismatched snapshots cannot replace a current quote', () => {
  const target=game({...offer,appid:620});
  const source={status:'ok',updatedAt:new Date(Date.now()+1000).toISOString(),data:{...offer,appid:620}};
  for(const invalid of [{...source,updatedAt:'2020-01-01T00:00:00Z'}, {...source,data:{...source.data,appid:730}}, {...source,data:{...source.data,currency:'USD'}}, {...source,data:{...source.data,final:-1}}]) {
    assert.equal(applySnapshot([target],snapshot(invalid)).applied,0);
    assert.equal(target.price.final,5000);
  }
  assert.throws(()=>applySnapshot([target],{...snapshot(source),version:2}));
});
test('failed snapshots retain actual quote dates and mark them stale', () => {
  const target=game({...offer,appid:620},{updatedAt:'2026-01-01T00:00:00Z'});
  applySnapshot([target],snapshot({status:'error',data:null,updatedAt:null,error:'timeout'}));
  assert.equal(target.price.final,5000);
  assert.equal(target.sources.steamPrice.updatedAt,'2026-01-01T00:00:00Z');
  assert.equal(state(target).stale,true);
});
test('paid offers age after three hours; non-price classifications after 26 hours', () => {
  assert.equal(state(game(offer,{updatedAt:new Date(Date.now()-4*3600000).toISOString()})).stale,true);
  const free={...offer,status:'free',isFree:true,final:0};
  assert.equal(state(game(free,{updatedAt:new Date(Date.now()-24*3600000).toISOString()})).stale,false);
  assert.equal(state(game(free,{updatedAt:new Date(Date.now()-27*3600000).toISOString()})).stale,true);
});
