'use client';
import {useEffect,useState} from 'react';
import {Button} from '@/components/ui/button';
import {Input} from '@/components/ui/input';
import {Textarea} from '@/components/ui/textarea';
import {NativeSelect as Select,NativeSelectOption as Option} from '@/components/ui/native-select';
type Value=Record<string,unknown>;
type Property={type?:string;enum?:string[];minimum?:number;maximum?:number;default?:unknown;format?:string};
export type InputSchema={properties:Record<string,Property>};
const title=(value:string)=>value.replaceAll('_',' ');
const base='/integrations/engine/api/evidence/artifacts/';

function ArtifactPicker({kind,value,onChange}:{kind:string;value:string;onChange:(v:string)=>void}){
  const [page,setPage]=useState(0),[items,setItems]=useState<{id:string;name:string}[]>([]),[total,setTotal]=useState(0),[error,setError]=useState('');
  useEffect(()=>{const controller=new AbortController();fetch(`${base}${kind}?offset=${page*50}`,{signal:controller.signal}).then(async r=>{if(!r.ok)throw new Error('Could not load saved '+kind);return await r.json() as {items:{id:string;name:string}[];total:number};}).then(r=>{setItems(r.items);setTotal(r.total);setError('');}).catch(e=>{if(!controller.signal.aborted)setError(e.message);});return()=>controller.abort();},[kind,page]);
  return <div><Select aria-label={'Saved '+title(kind)} value={value} onChange={e=>onChange(e.target.value)}><Option value="">Select saved {title(kind)}…</Option>{value&&!items.some(i=>i.id===value)&&<Option value={value}>{value}</Option>}{items.map(i=><Option key={i.id} value={i.id}>{i.name} · {i.id.slice(0,12)}</Option>)}</Select>{total>50&&<div><Button variant="ghost" disabled={!page} onClick={()=>setPage(page-1)}>Previous</Button><span>Page {page+1}</span><Button variant="ghost" disabled={(page+1)*50>=total} onClick={()=>setPage(page+1)}>Next</Button></div>}{error&&<span role="alert">{error}</span>}</div>;
}

function ReportsPicker({value,onChange}:{value:string[];onChange:(v:string[])=>void}){
  const [items,setItems]=useState<{id:string;name:string}[]>([]),[error,setError]=useState('');
  useEffect(()=>{const controller=new AbortController();fetch(base+'intelligence_document?limit=100',{signal:controller.signal}).then(async response=>{if(!response.ok)throw new Error('Could not load saved reports');return await response.json() as {items:{id:string;name:string}[];total:number};}).then(result=>{setItems(result.items);if(result.total>100)setError('Showing the latest 100 reports. Additional reports remain available in the artifact library.');}).catch(error=>{if(!controller.signal.aborted)setError(error.message);});return()=>controller.abort();},[]);
  return <fieldset className="col-span-full"><legend>Reports · leave unselected to search all reports for the company</legend><div className="mt-2 grid gap-2 md:grid-cols-2">{items.map(item=><label className="flex items-center gap-2 text-sm" key={item.id}><input type="checkbox" checked={value.includes(item.id)} disabled={!value.includes(item.id)&&value.length>=20} onChange={event=>onChange(event.target.checked?[...value,item.id]:value.filter(id=>id!==item.id))}/>{item.name}</label>)}</div>{!items.length&&!error&&<p>No reports yet. Choose “Freeze company report” to add one.</p>}{error&&<p role="status">{error}</p>}</fieldset>;
}

export function GuidedInputs({value,change,schema,action}:{value:Value;change:(v:Value)=>void;schema?:InputSchema;action:string}){
  const properties={...schema?.properties,...Object.fromEntries(Object.keys(value).map(k=>[k,schema?.properties[k]||{}]))};
  const idKinds:Record<string,string>={history_id:'quant_dataset',source_result_id:'quant_result',strategy_id:'strategy',dataset_id:'dataset',hypothesis_id:'hypothesis',report_id:'report',download_id:'download',...(action==='transition'?{id:'hypothesis'}:{}),...(action==='search-master'?{version:'instrument_master'}:{})};
  return <div className="flagship-fields">{Object.entries(properties).map(([key,property])=>{
    if(key==='pdf_base64')return null;
    if(action==='intelligence-index'&&['query','top_k'].includes(key))return null;
    const current=value[key]??property.default;
    if(current===undefined)return null; // Optional controls remain available in the complete JSON contract.
    const update=(next:unknown)=>change({...value,[key]:next});
    if(key==='index_id')return <label key={key}>Saved semantic index<ArtifactPicker kind="intelligence_index" value={String(current)} onChange={update}/></label>;
    if(key==='text'&&action==='intelligence-import')return <label key={key} className="col-span-full">Report text · or attach a PDF below<Textarea aria-label="Report text" rows={8} value={String(current)} onChange={e=>change({...value,text:e.target.value,pdf_base64:''})}/></label>;
    if(key==='document_ids')return <ReportsPicker key={key} value={Array.isArray(current)?current as string[]:[]} onChange={update}/>;
    if(key==='query'&&action.startsWith('intelligence-'))return <label key={key} className="col-span-full">Question or search terms<Textarea aria-label="Question or search terms" rows={2} value={String(current)} onChange={e=>update(e.target.value)}/></label>;
    if(key==='populations'&&Array.isArray(current))return <fieldset key={key} className="col-span-full"><legend>Household populations to compare</legend><div className="flex flex-wrap gap-3">{(current as number[]).map((population,index)=><label key={index}>Population {index+1}<Input type="number" min={1} max={1000000} step={1} value={population} onChange={e=>update(current.map((item,i)=>i===index?Number(e.target.value):item))}/><Button variant="ghost" disabled={current.length<=1} onClick={()=>update(current.filter((_,i)=>i!==index))}>Remove</Button></label>)}</div><Button variant="outline" disabled={current.length>=6} onClick={()=>update([...current,Math.min(1000000,Number(current.at(-1)||100)*10)])}>Add population</Button></fieldset>;
    const options=property.enum||(key==='partition'?['training','validation','holdout']:key==='state'?['draft','specified','testing','rejected','inconclusive','candidate for forward testing']:undefined);
    return <div key={key}><label className="block">{title(key)}{idKinds[key]?<ArtifactPicker kind={idKinds[key]} value={String(current)} onChange={update}/>:options?<Select value={String(current)} onChange={e=>update(e.target.value)}>{options.map(v=><Option key={v}>{v}</Option>)}</Select>:typeof current==='boolean'?<input type="checkbox" checked={current} onChange={e=>update(e.target.checked)}/>:typeof current==='number'?<Input type="number" step={property.type==='integer'?1:'any'} min={property.minimum} max={property.maximum} value={current} onChange={e=>update(Number(e.target.value))}/>:typeof current==='string'?<Input type={property.format==='date'||/^(train|validation|holdout)_(start|end)$/.test(key)?'date':'text'} value={current} onChange={e=>update(e.target.value)}/>:<span className="text-sm text-muted-foreground"> Edit the {Array.isArray(current)?'list':'structured fields'} in the complete specification below.</span>}</label></div>;
  })}</div>;
}
