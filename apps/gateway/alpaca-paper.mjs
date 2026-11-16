// This adapter can never address Alpaca's live trading or market-data hosts.
const ORIGIN='https://paper-api.alpaca.markets';
const pick=(value,keys)=>Object.fromEntries(keys.filter(k=>value[k]!==undefined).map(k=>[k,value[k]]));
export class AlpacaPaperAdapter {
  constructor({apiKey=process.env.ALPACA_PAPER_API_KEY||'',secretKey=process.env.ALPACA_PAPER_SECRET_KEY||'',request=fetch}={}){
    this.apiKey=apiKey;this.secretKey=secretKey;this.request=request;this.verified=false;this.checkedAt=null;this.accountId=null;
  }
  status(){return {connected:this.verified,state:this.verified?'connected':this.apiKey&&this.secretKey?'verification_required':'credentials_required',configured:!!(this.apiKey&&this.secretKey),mode:'Alpaca paper account · US / USD',dataProvider:'massive',executionProvider:'alpaca-paper',checkedAt:this.checkedAt,account:this.accountId?`…${this.accountId.slice(-4)}`:null,liveOrderSubmission:false,automatedDeploymentEnabled:false};}
  async get(endpoint,credentials={apiKey:this.apiKey,secretKey:this.secretKey}){
    if(!credentials.apiKey||!credentials.secretKey)throw new Error('Connect Alpaca using paper API credentials.');
    if(!['/v2/account','/v2/positions','/v2/orders?status=all&limit=100&direction=desc'].includes(endpoint))throw new Error('Unsupported Alpaca paper resource.');
    let response;
    try{response=await this.request(ORIGIN+endpoint,{method:'GET',headers:{'APCA-API-KEY-ID':credentials.apiKey,'APCA-API-SECRET-KEY':credentials.secretKey,Accept:'application/json'},redirect:'error',signal:AbortSignal.timeout(15000)});}catch{throw new Error('Alpaca paper API is unreachable.');}
    if(!response.ok){
      if([401,403].includes(response.status)&&credentials.apiKey===this.apiKey&&credentials.secretKey===this.secretKey)this.verified=false;
      throw new Error([401,403].includes(response.status)?'Alpaca paper access rejected. Check your paper API credentials.':`Alpaca paper API returned HTTP ${response.status}.`);
    }
    if(Number(response.headers.get('content-length'))>2_000_000)throw new Error('Alpaca paper response exceeds the size limit.');
    const reader=response.body.getReader(),chunks=[];let size=0;
    while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>2_000_000){await reader.cancel();throw new Error('Alpaca paper response exceeds the size limit.');}chunks.push(Buffer.from(value));}
    try{return JSON.parse(Buffer.concat(chunks).toString('utf8'));}catch{throw new Error('Alpaca returned an invalid paper response.');}
  }
  validateAccount(account){
    if(!account||typeof account.id!=='string'||account.currency!=='USD'||account.status!=='ACTIVE')throw new Error('An active USD Alpaca paper account is required.');
    if(account.trading_blocked||account.account_blocked||account.trade_suspended_by_user)throw new Error('Alpaca has blocked trading on this paper account.');
    for(const key of ['cash','equity','buying_power'])if(typeof account[key]!=='string'||!account[key].trim()||!Number.isFinite(Number(account[key])))throw new Error('Alpaca paper account balances are unavailable.');
  }
  async connect(input){
    const supplied=input.apiKey!==undefined||input.secretKey!==undefined;
    const apiKey=supplied?input.apiKey:this.apiKey,secretKey=supplied?input.secretKey:this.secretKey;
    if(![apiKey,secretKey].every(v=>typeof v==='string'&&/^[A-Za-z0-9_-]{8,200}$/.test(v)))throw new Error('Enter both Alpaca paper API keys.');
    // Invalidate before awaiting: a disconnect or a second connection must win.
    this.disconnect();const generation=this.generation;
    const account=await this.get('/v2/account',{apiKey,secretKey});this.validateAccount(account);
    if(generation!==this.generation)throw new Error('Alpaca connection changed; retry.');
    this.apiKey=apiKey;this.secretKey=secretKey;this.accountId=account.id;this.verified=true;this.checkedAt=new Date().toISOString();return this.status();
  }
  disconnect(){this.generation=(this.generation||0)+1;this.apiKey='';this.secretKey='';this.verified=false;this.accountId=null;this.checkedAt=null;return this.status();}
  async snapshot(){
    if(!this.verified)throw new Error('Verify the Alpaca paper connection first.');
    const generation=this.generation;
    const [account,positions,orders]=await Promise.all([this.get('/v2/account'),this.get('/v2/positions'),this.get('/v2/orders?status=all&limit=100&direction=desc')]);
    if(generation!==this.generation)throw new Error('Alpaca connection changed; retry.');
    this.validateAccount(account);
    if(account.id!==this.accountId||!Array.isArray(positions)||!Array.isArray(orders))throw new Error('Alpaca paper account response does not match this connection.');
    this.checkedAt=new Date().toISOString();
    return {source:'alpaca_paper',marketDataProvider:'massive',simulated:true,liveOrderSubmission:false,receivedAt:this.checkedAt,
      account:pick(account,['currency','cash','equity','last_equity','buying_power','portfolio_value','long_market_value','short_market_value','status']),
      positions:positions.map(p=>pick(p,['symbol','qty','side','avg_entry_price','market_value','unrealized_pl','current_price'])),
      orders:orders.map(o=>pick(o,['id','client_order_id','symbol','qty','side','type','time_in_force','status','filled_qty','filled_avg_price','submitted_at','filled_at','canceled_at'])),
      ordersScope:'Latest 100 orders; not a complete activity ledger',
    };
  }
}
