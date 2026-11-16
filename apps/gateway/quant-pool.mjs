import {Worker} from 'node:worker_threads';

/** One lazy worker; bounded admission keeps bulk research away from connection I/O. */
export class QuantPool {
  constructor({createWorker=()=>new Worker(new URL('./quant-worker.mjs',import.meta.url))}={}){this.createWorker=createWorker;this.worker=null;this.jobs=new Map();this.sequence=0;}
  failWorker(worker,message='Backtest worker stopped. Retry from the saved dataset.'){
    // A failed worker may emit error and then exit after its replacement starts.
    // Only reject work owned by that worker, never the replacement's jobs.
    for(const [id,job] of this.jobs){if(job.worker!==worker)continue;this.jobs.delete(id);job.reject(new Error(message));}
    if(this.worker===worker)this.worker=null;
  }
  run(strategy,bars,version){
    if(this.jobs.size>=3)return Promise.reject(new Error('Three Flagship backtests are already queued or running.'));
    if(!this.worker){
      const worker=this.createWorker();this.worker=worker;
      worker.on('message',message=>{const job=this.jobs.get(message.id);if(!job||job.worker!==worker)return;this.jobs.delete(message.id);message.error?job.reject(new Error(message.error)):job.resolve(message.result);if(![...this.jobs.values()].some(job=>job.worker===worker))worker.unref();});
      const fail=()=>this.failWorker(worker);
      worker.on('error',fail);worker.on('exit',fail);worker.unref();
    }
    const id=++this.sequence,worker=this.worker;worker.ref();
    return new Promise((resolve,reject)=>{
      this.jobs.set(id,{resolve,reject,worker});
      try{worker.postMessage({id,strategy,bars,version});}
      catch(error){this.jobs.delete(id);if(!this.jobs.size)worker.unref();reject(error);}
    });
  }
  close(){const worker=this.worker;if(worker){this.failWorker(worker);void worker.terminate();}}
}
export const quantPool=new QuantPool();
