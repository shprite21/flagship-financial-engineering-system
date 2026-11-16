import test from 'node:test';
import assert from 'node:assert/strict';
import {AlpacaPaperAdapter} from '../alpaca-paper.mjs';

const credentials={apiKey:'paper_key_fixture',secretKey:'paper_secret_fixture'};
const account={id:'fixture-account-1234',account_number:'private',currency:'USD',status:'ACTIVE',cash:'100000',equity:'100000',buying_power:'200000'};
const response=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'content-type':'application/json'}});
test('paper connection uses only fixed paper host, masks account, excludes credentials',async()=>{
  const calls=[];
  const adapter=new AlpacaPaperAdapter({apiKey:'',secretKey:'',request:async(url,options)=>{calls.push({url,options});return response(account);}});
  assert.equal(adapter.status().connected,false);
  const status=await adapter.connect(credentials);
  assert.equal(status.connected,true);assert.equal(status.account,'…1234');
  assert.equal(status.liveOrderSubmission,false);assert.equal(status.automatedDeploymentEnabled,false);
  assert.equal(calls[0].url,'https://paper-api.alpaca.markets/v2/account');
  assert.equal(calls[0].options.method,'GET');assert.equal(calls[0].options.redirect,'error');
  assert.equal(calls[0].options.headers['APCA-API-SECRET-KEY'],credentials.secretKey);
  for(const secret of [credentials.apiKey,credentials.secretKey,account.id,account.account_number])assert.ok(!JSON.stringify(status).includes(secret));
  for(const path of ['https://api.alpaca.markets/v2/account','/v2/orders/../account','/v2/account?apiKey=bad','/v2/orders/123'])await assert.rejects(adapter.get(path),/Unsupported/);
  adapter.disconnect();assert.equal(adapter.status().configured,false);
  await assert.rejects(adapter.snapshot(),/Verify/);
});
test('snapshots are labeled and sanitized, including external orders',async()=>{
  const adapter=new AlpacaPaperAdapter({request:async(url)=>response(url.endsWith('/account')?account:url.endsWith('/positions')?[{symbol:'SPY',qty:'1',side:'long',unrealized_pl:'-1',unknown_secret:'do-not-return'}]:[{id:'one',symbol:'SPY',client_order_id:'external-order',status:'filled',unknown_secret:'do-not-return'}])});
  await adapter.connect(credentials);const snapshot=await adapter.snapshot();
  assert.equal(snapshot.source,'alpaca_paper');assert.equal(snapshot.marketDataProvider,'massive');
  assert.equal(snapshot.simulated,true);assert.equal(snapshot.positions[0].unrealized_pl,'-1');
  assert.equal(snapshot.orders[0].client_order_id,'external-order');
  assert.ok(!JSON.stringify(snapshot).includes('do-not-return'));assert.equal(snapshot.account.account_number,undefined);
  assert.match(snapshot.ordersScope,/Latest 100/);
});
test('unauthorized and upstream errors cannot echo credentials',async()=>{
  for(const code of [401,403,429,500]){
    const adapter=new AlpacaPaperAdapter({request:async()=>response({message:credentials.secretKey},code)});
    await assert.rejects(adapter.connect(credentials),e=>!e.message.includes(credentials.secretKey));assert.equal(adapter.status().connected,false);
  }
  const adapter=new AlpacaPaperAdapter({request:async()=>{throw new Error(credentials.secretKey);}});
  await assert.rejects(adapter.connect(credentials),/unreachable/);
});
test('invalid or blocked accounts and malformed balances are rejected',async()=>{
  for(const override of [{currency:'INR'},{status:'SUSPENDED'},{trading_blocked:true},{account_blocked:true},{trade_suspended_by_user:true},{cash:'NaN'},{cash:''},{equity:null}]){
    const adapter=new AlpacaPaperAdapter({request:async()=>response({...account,...override})});
    await assert.rejects(adapter.connect(credentials));assert.equal(adapter.status().connected,false);
  }
});
test('disconnect wins against a pending connection and keys are not restored',async()=>{
  let finish;const adapter=new AlpacaPaperAdapter({request:()=>new Promise(resolve=>{finish=resolve;})});
  const pending=adapter.connect(credentials);adapter.disconnect();finish(response(account));
  await assert.rejects(pending,/changed/);assert.equal(adapter.status().configured,false);
});
test('changed credentials prevent stale snapshots after reconnect',async()=>{
  let defer=false;const completions=[];
  const adapter=new AlpacaPaperAdapter({request:async(url)=>{const data=url.endsWith('/account')?account:[];return defer?new Promise(resolve=>completions.push(()=>resolve(response(data)))):response(data);}});
  await adapter.connect(credentials);defer=true;const pending=adapter.snapshot();adapter.disconnect();for(const finish of completions)finish();
  await assert.rejects(pending,/changed/);
});
test('environment-supplied credentials still require explicit verification',async()=>{
  const adapter=new AlpacaPaperAdapter({...credentials,request:async()=>response(account)});
  assert.equal(adapter.status().connected,false);assert.equal(adapter.status().configured,true);
  await adapter.connect({});assert.equal(adapter.status().connected,true);
});
test('oversized and invalid provider responses fail closed',async()=>{
  for(const make of [()=>new Response('invalid'),()=>new Response('{}',{headers:{'content-length':'2000001'}}),()=>new Response('x'.repeat(2000001))]){
    const adapter=new AlpacaPaperAdapter({request:async()=>make()});await assert.rejects(adapter.connect(credentials));assert.equal(adapter.status().connected,false);
  }
});
