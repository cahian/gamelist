const {test} = require('node:test');
const assert = require('node:assert/strict');
const {state,render} = require('../prices.js');
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
