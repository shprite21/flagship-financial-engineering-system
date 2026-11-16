'use client';

type Citation = {citation:string;document_id:string;company:string;report:string;period:string;page:number;excerpt:string};
const base='/integrations/engine/api/evidence';

export function ReportEvidence({artifact,id,kind}:{artifact:Record<string,unknown>;id:string;kind:string}) {
  const result=artifact.results as Record<string,{citations?:Citation[]}>|undefined;
  const hits=result?.['Report evidence']?.citations;
  const metadata=artifact.metadata as Record<string,string>|undefined;
  const news=(artifact.results as {News?:{sources?:{title:string;url:string;published_date:string;content:string}[]}}|undefined)?.News?.sources;
  return <>
    {kind==='intelligence_document'&&metadata&&<div className="space-y-3">
      <p>{metadata.company} · {metadata.report} · {metadata.period||'Period unspecified'} · Publication date supplied: {metadata.published||'unknown'}</p>
      <p>{Array.isArray(artifact.pages)?artifact.pages.length:0} pages frozen. Metadata has not been independently verified.</p>
      <a className="button secondary" href={`${base}/documents/${id}/source`} target="_blank" rel="noreferrer">Open original report</a>
    </div>}
    {typeof artifact.answer==='string'&&<section className="flagship-panel"><h3>Local AI answer · verify against the cited pages</h3><p className="whitespace-pre-wrap">{artifact.answer}</p></section>}
    {typeof artifact.message==='string'&&<p>{artifact.message}</p>}
    {news&&<div className="space-y-4">{news.map((item,i)=><article className="flagship-panel" key={i}><a href={item.url} target="_blank" rel="noreferrer" className="underline">{item.title||'News source'} ↗</a><p>{item.published_date||'Publication date unavailable'}</p><p>{item.content}</p></article>)}</div>}
    {hits&&<div className="space-y-4">{hits.map(hit=><article key={hit.citation} className="flagship-panel">
      <div className="flagship-toolbar"><h3>[{hit.citation}] {hit.company} · {hit.report}</h3><a className="button secondary" href={`${base}/documents/${hit.document_id}/source#page=${hit.page}`} target="_blank" rel="noreferrer">Page {hit.page} ↗</a></div>
      <p className="whitespace-pre-wrap text-sm leading-relaxed">{hit.excerpt}</p>
      <small>Original page text · columns and units may require checking in the PDF</small>
    </article>)}</div>}
  </>;
}
