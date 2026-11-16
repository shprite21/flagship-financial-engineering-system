# Company intelligence in Q

Open **Company intelligence** in Q. The workbench supports report import, lexical search, local semantic indexing/search, cited local AI answers and explicit news retrieval. All actions use the existing private engine, bounded research queue and immutable artifact registry.

## Frozen reports

PDF imports preserve original bytes, SHA-256, supplied company/report/period/publication metadata, extracted page text, parser version and text hash. New imports also retain the extraction-worker hash. PDF extraction runs in a separate process with a two-minute limit and no provider credential environment. Scanned or encrypted reports fail explicitly; there is no invented OCR output. Text imports use form-feed characters as page separators.

PDF extraction does not establish table layout, column association, currency or units. The UI links every result to the original PDF page. Labels and publication dates inherited from the source project's catalogue are **supplied, unverified metadata**. The as-of filter excludes unknown/later supplied publication dates; it does not establish historical availability or make these reports valid point-in-time strategy inputs.

Browser uploads accept PDFs up to 2 MB within Q's existing request limit. Larger local source reports, up to 50 MiB each, can be imported explicitly from the original project's catalogue:

```powershell
cd apps/engine
.\.venv\Scripts\python.exe -m scripts.import_company_reports 'C:\quant\projects\Competitive-Market-Intelligence-System' --record '../../outputs/consolidation/imported-reports.json'
```

The importer resolves only files inside that project's Reports directory and never modifies them. Q's copies live under `.data/flagship/evidence/report-sources`; they are private local state, absent from source control. Six cached source PDFs were imported, totaling 1,089 pages. Earlier and later imports remain distinct when extraction identity changes.

## Search and semantic retrieval

Lexical search needs no external service. It searches explicitly selected documents or the chosen company's documents, with period and supplied publication-date filters. Page-local windows are 1,800 characters with 200-character overlap. BM25 uses k1=1.5 and b=0.75. Query tokens and tie breaks are ordered deterministically; output contains at most one excerpt per page. No matches produces an explicit empty result. Search exports retain the exact documents used, so later imports cannot change a saved result.

Semantic indexing preserves the source project's embedding-based retrieval capability using local Q storage. Configure `Q_INTELLIGENCE_EMBEDDING_MODEL` on the backend with the name of an already installed local Ollama model. An index contains at most 2,000 chunks, batched by eight, with exact excerpts, normalized finite vectors, dimensions and the model's digest. Input truncation is disabled. The model is checked before and after encoding; changes or unavailable models fail. Search requires the same model digest and stores the query vector. Cosine similarity is a retrieval ordering, not confidence that a fact is correct.

Q does not copy the source project's Pinecone credentials or remote index. Existing remote data remains untouched. The local index is a replacement storage adapter for the same report-retrieval capability.

## Optional providers

- `Q_INTELLIGENCE_OLLAMA_MODEL`: an already installed local chat model. The explicit answer action sends only the question and selected excerpts to `127.0.0.1:11434`, with no tools. It requests JSON and checks that cited identifiers exist and appear in the answer. The answer remains visibly AI-generated and unverified; citation validation is not factual validation. An optional semantic index can supply excerpts.
- `Q_INTELLIGENCE_EMBEDDING_MODEL`: the installed local embedding model used by index/search actions.
- `Q_INTELLIGENCE_TAVILY_API_KEY`: backend-only news credential. The explicit news action calls Tavily and saves actual returned sources, dates, snippets and retrieval time. It requests no generated answer. It is not a historical news dataset.

These variables belong to the backend process, never browser state or source control. Restart the local launcher after changing them. Configuration is not proof of connectivity. Missing providers fail honestly; they never produce sample AI answers, vectors or news. No optional provider is required for lexical search or native economy research.

Provider contracts: [Ollama embeddings](https://docs.ollama.com/api/embed), [Ollama model identity](https://docs.ollama.com/api/tags), [Tavily search](https://docs.tavily.com/documentation/api-reference/endpoint/search).

## Reproduction and boundaries

`python -m qmodules.replay EXPORT.json` replays lexical search from frozen documents and semantic ranking from frozen document/query vectors without contacting a model. It verifies source/dependency fingerprints and immutable input identities. It does not claim to reproduce model generation. AI answers and news are retained observations, not deterministic replay actions.

Report contents are untrusted evidence. Nothing in a report authorizes tools, configuration changes, strategy promotion, or orders. Neither company intelligence nor semantic relevance is a trading signal without a separately specified and temporally validated strategy.
