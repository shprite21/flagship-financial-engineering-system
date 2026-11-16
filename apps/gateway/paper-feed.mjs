// Provider adapters publish atomic, credential-free raw-data envelopes here.
// This is separate from historical caches and never synthesizes a market feed.
import {readFile, realpath} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../.data/paper-feeds');
export async function paperFeed(provider,market,interval,directory=root){
  if(!/^[a-zA-Z0-9_-]{1,64}$/.test(provider||'')||!['US','IN'].includes(market)||!['1d','1m'].includes(interval))throw new Error('Invalid paper feed selection.');
  let base,file;
  try{base=await realpath(directory);file=await realpath(path.join(base,`${provider}-${market}-${interval}.json`));}
  catch{throw new Error('Paper provider is not configured. Historical caches are not executable paper feeds.');}
  if(path.dirname(file)!==base)throw new Error('Paper feed must remain inside its provider directory.');
  const data=await readFile(file);
  if(data.length>32_000_000)throw new Error('Paper feed exceeds 32 MB.');
  const feed=JSON.parse(data.toString('utf8'));
  if(feed.provider!==provider||feed.market!==market||feed.interval!==interval||feed.price_basis!=='raw')throw new Error('Paper feed identity or price basis mismatch.');
  return feed;
}
