"""Predeclared small candidate comparison, date-grouped purged walk-forward.

Public daily bars provide retrospective proxy evidence only. CPU inference uses
plain numeric arrays; loading a checkpoint never executes Python/pickle content.
"""
import hashlib
import json
import os
import platform
import zipfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .costs import Costs, size_trade
from .data import FEATURES, features, save_json, sha

CANDIDATES = ('momentum', 'linear', 'mlp')
PROTOCOL = dict(train_days=504, validation_days=126, test_days=63, final_days=126,
                embargo_days=5, threshold=.60, seeds=[17,29], max_epochs=120,
                learning_rate=.003, weight_decay=.03, min_trades=30,
                cash=5000, planned_loss=50, weekly_loss=150, max_positions=1,
                min_adv_inr=100_000_000, max_participation=.0001,
                api_monthly_including_gst=588.82,
                settlement='Conservative: sale proceeds released after one further complete observed session',
                selection='net rupees minus half maximum drawdown; positive doubled-slippage result and most folds positive')


def sigmoid(x):
    return 1/(1+np.exp(-np.clip(x,-40,40)))


def outcome(row, cash=5000., remaining=50., costs=None):
    costs=costs or Costs()
    if pd.isna(row.next_open) or row.adv20 < PROTOCOL['min_adv_inr']:
        return None
    entry=float(row.next_open)*(1+costs.slippage_bps/10000)
    stop=entry*(1-float(row.stop_fraction))
    sized=size_trade(entry,stop,min(cash,5000.),min(remaining,50.),costs)
    q=sized['quantity']
    if not q or q*entry > row.adv20*PROTOCOL['max_participation']:
        return None
    # Stop-first, no profit target. Daily stop fills remain an explicit proxy;
    # stressed exit slippage cannot bound a real gap/circuit/late manual exit.
    exit_price=(stop if row.next_low <= stop else float(row.next_close))*(1-costs.slippage_bps/10000)
    fees=costs.roundtrip(q,entry,exit_price)
    return dict(date=str(row.next_date), symbol=row.symbol, quantity=q, entry=entry, exit=exit_price,
                gross=q*(exit_price-entry), fees=fees, net=q*(exit_price-entry)-fees,
                planned_loss=sized['planned_loss'], stopped=bool(row.next_low<=stop))


def prepare(frame):
    f=features(frame).dropna(subset=['next_date','next_open','next_low','next_close','label_end']).copy()
    dates=sorted(frame.date.unique())
    next_observed=dict(zip(dates[:-1],dates[1:]))
    f=f[f.next_date==f.date.map(next_observed)].copy()
    f['target']=[float((o or {'net':-1})['net']>0) for o in (outcome(row) for row in f.itertuples())]
    return f.reset_index(drop=True)


def partitions(f, protocol=PROTOCOL):
    dates=sorted(f.date.unique())
    minimum=protocol['train_days']+protocol['validation_days']+protocol['test_days']+protocol['final_days']
    if len(dates)<minimum:
        raise ValueError(f'Need at least {minimum} common chronological sessions; have {len(dates)}')
    final_start=len(dates)-protocol['final_days']
    folds=[]
    for test_start in range(protocol['train_days']+protocol['validation_days'], final_start, protocol['test_days']):
        test_end=min(test_start+protocol['test_days'],final_start)
        if test_end-test_start<protocol['test_days']:
            break
        val_start=test_start-protocol['validation_days']
        train=f[(f.date<dates[val_start-protocol['embargo_days']]) &
                (f.label_end < f.loc[f.date==dates[val_start],'signal_time'].min())]
        validation=f[(f.date>=dates[val_start]) & (f.date<dates[test_start-protocol['embargo_days']]) &
                     (f.label_end<f.loc[f.date==dates[test_start],'signal_time'].min())]
        test=f[(f.date>=dates[test_start]) & (f.date<=dates[test_end-1])]
        # Labels from the last test day may reach the final holdout: purge them too.
        boundary=f.loc[f.date==dates[final_start],'signal_time'].min()
        test=test[test.label_end<boundary]
        folds.append((train,validation,test))
    return folds, f[f.date>=dates[final_start]], dates[final_start]


def fit(train, validation, kind, seed, device='cuda'):
    if kind=='momentum':
        eligible=(train.ret20>0)&(train.trend>0)
        p=float((train.loc[eligible,'target'].sum()+1)/(eligible.sum()+2))
        return dict(kind=kind,probability=p,features=FEATURES,seed=seed)
    import torch
    if device=='cuda' and not torch.cuda.is_available():
        raise ValueError('GPU unavailable; choose --device cpu explicitly for a CPU-only diagnostic')
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
    torch.manual_seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32=False
    x=train[FEATURES].to_numpy(np.float32)
    mean=x.mean(0); scale=np.maximum(x.std(0),1e-5)
    # Calibration uses the later half of validation, never early-stop data/test.
    days=sorted(validation.date.unique()); cut=days[len(days)//2]
    early=validation[(validation.date<cut)&(validation.label_end<validation.loc[validation.date==cut,'signal_time'].min())]
    calibration=validation[validation.date>=cut]
    tensor=lambda a: torch.as_tensor(a,dtype=torch.float32,device=device)
    tx=tensor(np.clip((x-mean)/scale,-8,8)); ty=tensor(train.target.to_numpy()).reshape(-1,1)
    vx=tensor(np.clip((early[FEATURES].to_numpy()-mean)/scale,-8,8)); vy=tensor(early.target.to_numpy()).reshape(-1,1)
    model=(torch.nn.Sequential(torch.nn.Linear(len(FEATURES),1)) if kind=='linear' else
           torch.nn.Sequential(torch.nn.Linear(len(FEATURES),16),torch.nn.Tanh(),torch.nn.Dropout(.20),torch.nn.Linear(16,1))).to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=PROTOCOL['learning_rate'],weight_decay=PROTOCOL['weight_decay'])
    loss=torch.nn.BCEWithLogitsLoss()
    best,wait,best_state,best_epoch=float('inf'),0,None,0
    for epoch in range(PROTOCOL['max_epochs']):
        model.train(); optimizer.zero_grad(); loss(model(tx),ty).backward(); optimizer.step()
        model.eval()
        with torch.no_grad(): score=float(loss(model(vx),vy).cpu())
        if score<best-1e-5:
            best,wait,best_epoch=score,0,epoch+1
            best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        else:
            wait+=1
        if wait>=15: break
    if best_state is None: raise ValueError('Training failed to produce finite validation loss')
    model.load_state_dict(best_state); model.eval()
    layers=[]
    for module in model:
        if isinstance(module,torch.nn.Linear):
            layers.append({'weight':module.weight.detach().cpu().numpy().tolist(),'bias':module.bias.detach().cpu().numpy().tolist()})
    checkpoint=dict(kind=kind,features=FEATURES,mean=mean.tolist(),scale=scale.tolist(),layers=layers,temperature=1.,
                    seed=seed,epochs=best_epoch,training_device=device,torch=torch.__version__,cuda=torch.version.cuda)
    logits=raw_logits(checkpoint,calibration)
    y=calibration.target.to_numpy()
    grid=[.75,1.,1.5,2.,3.]
    checkpoint['temperature']=min(grid,key=lambda t:float(np.mean(np.logaddexp(0,logits/t)-y*logits/t)))
    with torch.no_grad(): gpu=model(tensor(np.clip((calibration[FEATURES].to_numpy()-mean)/scale,-8,8))).cpu().numpy().ravel()
    error=float(np.max(np.abs(gpu-logits)))
    if error>2e-5: raise ValueError('CPU inference parity failed')
    checkpoint['cpu_parity_max_logit_error']=error
    return checkpoint


def raw_logits(checkpoint, frame):
    x=np.clip((frame[checkpoint['features']].to_numpy()-np.array(checkpoint['mean']))/np.array(checkpoint['scale']),-8,8)
    for i,layer in enumerate(checkpoint['layers']):
        x=x@np.array(layer['weight']).T+np.array(layer['bias'])
        if i<len(checkpoint['layers'])-1: x=np.tanh(x)
    return x.ravel()


def predict(checkpoint,frame):
    if checkpoint['kind']=='momentum': return np.full(len(frame),checkpoint['probability'])
    return sigmoid(raw_logits(checkpoint,frame)/checkpoint['temperature'])


def calibration_metrics(y,p):
    if not len(y): return {'brier':None,'ece':None,'n':0}
    ece=0.
    for left in np.arange(0,1,.1):
        mask=(p>=left)&(p<left+.1) if left<.9 else (p>=left)&(p<=1)
        if mask.any(): ece+=mask.mean()*abs(p[mask].mean()-y[mask].mean())
    return {'brier':float(np.mean((p-y)**2)), 'ece':float(ece), 'n':len(y)}


def simulate(f,p,kind,costs=None):
    costs=costs or Costs()
    f=f.copy(); f['probability']=p
    cash,peak,drawdown=5000.,5000.,0.
    weekly={}; trades=[]; curve=[]; unsettled=[]
    for session_index,(day,g) in enumerate(f.groupby('date',sort=True)):
        cash+=sum(amount for due,amount in unsettled if due<=session_index)
        unsettled=[(due,amount) for due,amount in unsettled if due>session_index]
        if kind=='momentum':
            g=g[(g.ret20>0)&(g.trend>0)].sort_values(['ret20','symbol'],ascending=[False,True])
        else:
            g=g[g.probability>=PROTOCOL['threshold']].sort_values(['probability','symbol'],ascending=[False,True])
        for row in g.itertuples():
            week=str(pd.Timestamp(row.next_date).isocalendar()[:2])
            remaining=150.-weekly.get(week,0.)
            trade=outcome(row,cash,min(50.,remaining),costs)
            if not trade: continue
            buy_cost=trade['quantity']*trade['entry']+costs.leg(trade['quantity']*trade['entry'],'buy')['total']
            proceeds=trade['quantity']*trade['exit']-costs.leg(trade['quantity']*trade['exit'],'sell')['total']
            cash-=buy_cost; unsettled.append((session_index+2,proceeds))
            weekly[week]=weekly.get(week,0.)+max(0.,-trade['net'])
            trades.append({**trade,'probability':row.probability})
            break
        equity=cash+sum(amount for due,amount in unsettled)
        peak=max(peak,equity); drawdown=max(drawdown,peak-equity)
        curve.append({'signal_date':day,'equity':equity,'available_cash':cash,'unsettled_proceeds':equity-cash})
    equity=cash+sum(amount for due,amount in unsettled)
    return dict(net_inr=equity-5000.,return_fraction=equity/5000.-1,max_drawdown_inr=drawdown,
                trade_count=len(trades),win_rate=sum(t['net']>0 for t in trades)/len(trades) if trades else None,
                total_fees=sum(t['fees'] for t in trades),trades=trades,curve=curve)


def device_report(device):
    import torch
    result={'requested_device':device,'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
            'torch':torch.__version__,'cuda_runtime':torch.version.cuda,'cuda_available':torch.cuda.is_available()}
    if device=='cuda':
        if not torch.cuda.is_available(): raise ValueError('CUDA unavailable; no GPU results produced')
        result.update(gpu=torch.cuda.get_device_name(0),capability=list(torch.cuda.get_device_capability(0)),arch_list=torch.cuda.get_arch_list())
        x=torch.randn(64,64,device='cuda',requires_grad=True); (x@x.T).sum().backward(); torch.cuda.synchronize()
        result['forward_backward_ok']=bool(torch.isfinite(x.grad).all())
    return result


def run(root,dataset,device='cuda'):
    root=Path(root); source=root/'datasets'/dataset
    raw=(source/'bars.csv').read_bytes()
    if sha(raw)!=dataset: raise ValueError('Dataset checksum mismatch')
    manifest=json.loads((source/'manifest.json').read_text())
    runtime=device_report(device)
    f=prepare(pd.read_csv(source/'bars.csv'))
    # Strict common dates prevent comparing different universes across folds.
    counts=f.groupby('date').symbol.nunique(); common=counts[counts==len(manifest['symbols'])].index
    f=f[f.date.isin(common)].reset_index(drop=True)
    folds,final,cutoff=partitions(f)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=root/'runs'/stamp; out.mkdir(parents=True,exist_ok=False)
    save_json(out/'dataset-manifest.json',manifest)
    source_hash=sha(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py'))))
    with zipfile.ZipFile(out/'source.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(Path(__file__).parent.glob('*.py')): archive.write(p,'india/'+p.name)
    save_json(out/'protocol.json',{'protocol':PROTOCOL,'dataset':dataset,'final_cutoff':cutoff,'source_sha256':source_hash,'runtime':runtime})
    reports=[]
    for kind in CANDIDATES:
        all_frames=[]; all_prob=[]; fold_reports=[]; seed_reports=[]
        for number,(train,val,test) in enumerate(folds):
            seeds=[17] if kind=='momentum' else PROTOCOL['seeds']
            predictions=[]
            for seed in seeds:
                checkpoint=fit(train,val,kind,seed,device)
                checkpoint.update(dataset=dataset,source_sha256=source_hash,trained_through=train.date.max(),calibrated_through=val.date.max())
                save_json(out/f'{kind}-fold{number}-seed{seed}.json',checkpoint)
                prob=predict(checkpoint,test); predictions.append(prob)
                trial=simulate(test,prob,kind)
                seed_reports.append({'fold':number,'seed':seed,'net_inr':trial['net_inr'],'trade_count':trial['trade_count']})
            p=np.mean(predictions,axis=0)
            trial=simulate(test,p,kind)
            fold_reports.append({'fold':number,'train_end':train.date.max(),'validation_start':val.date.min(),'validation_end':val.date.max(),
                'test_start':test.date.min(),'test_end':test.date.max(),'net_inr':trial['net_inr'],'trades':trial['trade_count'],
                **calibration_metrics(test.target.to_numpy(),p)})
            all_frames.append(test); all_prob.extend(p.tolist())
            print(json.dumps({'candidate':kind,'fold':number,'net_inr':round(trial['net_inr'],2),'trades':trial['trade_count']}),flush=True)
        combined=pd.concat(all_frames); probs=np.array(all_prob)
        replay=simulate(combined,probs,kind)
        stress=simulate(combined,probs,kind,replace(Costs(),slippage_bps=20.))
        calibration=calibration_metrics(combined.target.to_numpy(),probs)
        # Prevalence comparator fitted separately per training fold.
        null_p=np.concatenate([np.full(len(t),tr.target.mean()) for tr,v,t in folds])
        null_brier=calibration_metrics(combined.target.to_numpy(),null_p)['brier']
        positive=sum(x['net_inr']>0 for x in fold_reports)
        months=len(set(combined.date.str[:7]))
        api_overhead=months*PROTOCOL['api_monthly_including_gst']
        all_in_net=replay['net_inr']-api_overhead
        eligible=(replay['trade_count']>=30 and replay['net_inr']>0 and stress['net_inr']>0 and positive>=max(3,.6*len(folds))
                  and all_in_net>0
                  and (kind=='momentum' or calibration['brier']<null_brier))
        reports.append({'candidate':kind,**replay,'calibration':calibration,'null_brier':null_brier,'folds':fold_reports,
                        'api_overhead_scenario_inr':api_overhead,'net_after_api_scenario_inr':all_in_net,
                        'auto_squareoff_extra_per_incident_inr':59.,
                        'seed_diagnostics':seed_reports,'stress_net_inr':stress['net_inr'],'research_eligible':eligible})
    eligible=[r for r in reports if r['research_eligible']]
    winner=max(eligible,key=lambda r:r['net_inr']-.5*r['max_drawdown_inr'])['candidate'] if eligible else None
    # Final segment is used once for the development-selected candidate only.
    holdout=None; model_files=[]
    if winner:
        dates=sorted(f[f.date<cutoff].date.unique()); val_start=dates[-PROTOCOL['validation_days']]
        tr=f[(f.date<dates[-PROTOCOL['validation_days']-5])&(f.label_end<pd.Timestamp(val_start+' 00:00:00',tz='UTC'))]
        val=f[(f.date>=val_start)&(f.date<dates[-5])&(f.label_end<pd.Timestamp(cutoff+' 00:00:00',tz='UTC'))]
        probabilities=[]
        for seed in ([17] if winner=='momentum' else PROTOCOL['seeds']):
            model=fit(tr,val,winner,seed,device)
            model.update(dataset=dataset,source_sha256=source_hash,trained_through=tr.date.max(),calibrated_through=val.date.max())
            filename=f'selected-seed{seed}.json'; save_json(out/filename,model); model_files.append(filename)
            probabilities.append(predict(model,final))
        holdout=simulate(final,np.mean(probabilities,axis=0),winner)
        holdout['calibration']=calibration_metrics(final.target.to_numpy(),np.mean(probabilities,axis=0))
    report={'id':stamp,'created_at':datetime.now(timezone.utc).isoformat(),'dataset':dataset,'source_sha256':source_hash,
        'protocol':PROTOCOL,'runtime':runtime,'costs':Costs().snapshot(),'data_first':f.date.min(),'data_last':f.next_date.max(),
        'final_cutoff':cutoff,'final_revealed':bool(winner),'selected_candidate':winner,'candidates':reports,'holdout':holdout,
        'cost_basis':'Current tariff applied uniformly to historical proxy trades, not a reconstruction of historical brokerage.',
        'fixed_cost_basis':'API scenario assumes INR 588.82 every evaluated calendar month, paid outside trading cash. No subscription bought. If funded from INR 5000, first-month cash falls to INR 4411.18; deployment remains blocked.',
        'model_files':model_files,'live_eligible':False,'decision':'NO TRADE',
        'cash_reference':{'net_inr':0.,'trades':0,'fees':0.,'basis':'No trade, no paid API subscription, no interest assumed'},
        'blockers':(['No candidate passed predeclared development criteria'] if not winner else [])+
                   manifest['limitations']+['Authenticated executable quote/depth and prospective manual fill calibration unavailable',
                   'Selection across three candidates is exploratory; no independent prospective edge established',
                   'Final retrospective evidence is not permission to trade'],
        'options':'Disabled: no verified current contract/lot/premium/spread, and full premium loss must fit INR 50 including charges'}
    save_json(out/'report.json',report)
    checks={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()}
    save_json(out/'checksums.json',checks)
    return report
