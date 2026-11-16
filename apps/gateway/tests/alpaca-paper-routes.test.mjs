import test from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {createGateway} from '../server.mjs';

test('Alpaca connection routes require same-origin writes and expose no order route',async()=>{
  let connected=false;
  const alpaca={status:()=>({connected,liveOrderSubmission:false}),connect:async input=>{assert.equal(input.apiKey,'fixture-key');connected=true;return alpaca.status();},disconnect:()=>{connected=false;return alpaca.status();},snapshot:async()=>({source:'alpaca_paper',positions:[],orders:[]})};
  const gateway=createGateway({alpaca,codex:{stop(){}},engine:{stop(){}}});gateway.listen(0,'127.0.0.1');await once(gateway,'listening');
  const base=`http://127.0.0.1:${gateway.address().port}/integrations/alpaca-paper`;
  const post=(route,body,origin='http://127.0.0.1:5273')=>fetch(base+route,{method:'POST',headers:{'Content-Type':'application/json',Origin:origin},body:JSON.stringify(body)});
  try{
    assert.equal((await post('/connect',{apiKey:'fixture-key'},'https://untrusted.example')).status,403);assert.equal(connected,false);
    assert.equal((await post('/connect',{apiKey:'fixture-key'})).status,200);
    assert.equal((await (await fetch(base+'/status')).json()).connected,true);
    assert.equal((await (await fetch(base+'/account')).json()).source,'alpaca_paper');
    assert.equal((await post('/orders',{symbol:'SPY',qty:1})).status,404);
    await post('/disconnect',{});assert.equal(connected,false);
  }finally{await new Promise(resolve=>gateway.close(resolve));}
});
