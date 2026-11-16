import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {paperFeed} from '../paper-feed.mjs';

test('paper feeds are explicit and never fall back to historical caches',async()=>{
  const root=await mkdtemp(path.join(os.tmpdir(),'q-paper-feed-'));
  try{
    await assert.rejects(()=>paperFeed('../secret','US','1d',root),/Invalid/);
    await assert.rejects(()=>paperFeed('missing','US','1d',root),/not configured/);
    const input={provider:'fixture',market:'US',interval:'1d',price_basis:'raw',source:'synthetic test fixture'};
    await writeFile(path.join(root,'fixture-US-1d.json'),JSON.stringify(input));
    assert.deepEqual(await paperFeed('fixture','US','1d',root),input);
    await writeFile(path.join(root,'fixture-US-1d.json'),JSON.stringify({...input,price_basis:'adjusted'}));
    await assert.rejects(()=>paperFeed('fixture','US','1d',root),/mismatch/);
  }finally{await rm(root,{recursive:true,force:true});}
});
