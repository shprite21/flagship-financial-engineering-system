import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {QuantPool} from '../quant-pool.mjs';

class ControlledWorker extends EventEmitter {
  messages=[];
  ref(){}
  unref(){}
  terminate(){return Promise.resolve(0);}
  postMessage(message){this.messages.push(message);}
  complete(result){this.emit('message',{id:this.messages.at(-1).id,result});}
}

test('a failed worker exiting late cannot reject accepted replacement work',async()=>{
  const workers=[];
  const pool=new QuantPool({createWorker:()=>{const worker=new ControlledWorker();workers.push(worker);return worker;}});
  const failed=pool.run({},[],'first');
  const rejection=assert.rejects(failed,/worker stopped/);
  workers[0].emit('error',new Error('fixture failure'));
  await rejection;
  const replacement=pool.run({},[],'replacement');
  workers[0].emit('exit',1);
  assert.equal(pool.jobs.size,1);
  workers[1].complete({version:'replacement'});
  assert.deepEqual(await replacement,{version:'replacement'});
  pool.close();
});

test('serialization failures release admission capacity and subsequent work completes',async()=>{
  const worker=new ControlledWorker();
  worker.postMessage=()=>{throw new DOMException('Cannot clone fixture','DataCloneError');};
  const pool=new QuantPool({createWorker:()=>worker});
  for(let i=0;i<4;i++)await assert.rejects(pool.run({},[],String(i)),{name:'DataCloneError'});
  assert.equal(pool.jobs.size,0);
  worker.postMessage=ControlledWorker.prototype.postMessage;
  const result=pool.run({},[],'valid');
  worker.complete('completed');
  assert.equal(await result,'completed');
  pool.close();
});

test('closing a busy pool settles its jobs without waiting for worker exit',async()=>{
  const pool=new QuantPool({createWorker:()=>new ControlledWorker()});
  const work=pool.run({},[],'pending');
  const rejected=assert.rejects(work,/worker stopped/);
  pool.close();
  assert.equal(pool.jobs.size,0);
  assert.equal(pool.worker,null);
  await rejected;
});
