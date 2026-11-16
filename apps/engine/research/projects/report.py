"""Artifact-derived Markdown and reproducibility exports; no generated conclusions."""
import io
import json
import zipfile

from evidence.storage import digest, now


def block(value):
    return '```json\n' + json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n```'


def markdown(project, comparisons):
    spec, thesis = project['spec'], project['spec']['thesis']
    trials = project['trials']
    validation = [{'trial_id': v['trial_id'], 'id': v['id'], 'status': v['status'],
                   'summary': v['result']['summary'] if v['result'] else None} for v in project['validations']]
    layers = lambda ids: [{'validation_id': v['id'], 'layer': l} for v in project['validations'] if v['result']
                         for l in v['result']['layers'] if l['id'] in ids]
    sections = [
        ('Abstract', f"Automated evidence draft for {thesis['title']}. {len(trials)} explicit trial attempts are retained. No profitability conclusion is generated.\n\nResearcher interpretation: not supplied."),
        ('Research Question', thesis['research_question']), ('Motivation', thesis['mechanism']),
        ('Literature Review', block(project['references']) if project['references'] else 'No sources registered. No citations are invented.'),
        ('Hypothesis', block({'economic_hypothesis': thesis['economic_hypothesis'], 'alpha_source': thesis['alpha_source'],
                              'failure_conditions': thesis['failure_conditions'], 'revisions': project['revisions']})),
        ('Data', block(project['datasets'])), ('Methodology', block({'specification': spec, 'integrity': project['integrity']})),
        ('Signal Construction', block({'catalogue': spec['research']['sleeves'], 'researcher_notes': spec['signal_notes'],
            'implementation': 'Existing Q catalogue strategy; notes do not replace executable code.'})),
        ('Portfolio Construction', block({'mandate': spec['research'], 'researcher_notes': spec['portfolio_notes']})),
        ('Backtesting Protocol', block([{'trial_id': t['id'], 'status': t['status'], 'reason': t['reason'],
            'request': t['request'], 'error': t['error'], 'metrics': t['result']['metrics'] if t['result'] else None,
            'execution': t['result']['provenance'].get('execution') if t['result'] else None} for t in trials])),
        ('Statistical Validation', block({'runs': validation, 'layers': layers({7, 8, 9, 10, 12})})),
        ('Robustness Analysis', block({'layers': layers({4, 5, 6, 13, 14, 16}), 'all_survival_parameter_attempts': project['diagnostic_trials']})),
        ('Regime Analysis', block(layers({11}))),
        ('Walk-Forward / OOS Results', block({'walk_forward': layers({2, 3}), 'reserved_oos': project['oos'],
            'reveal_events': [e for e in project['journal'] if e['action'] == 'oos_revealed'],
            'genuinely_unseen': 'UNKNOWN: prior exposure outside Q is not independently established'})),
        ('Execution Assumptions', block(layers({5, 6}))),
        ('Prospective Validation', block({'registrations': project['forward'], 'versions': project['freezes'],
                                          'evidence': [c['forward'] for c in comparisons]})),
        ('Expected vs Realized Performance', block(comparisons)),
        ('Limitations', thesis['limitations'] + '\n\nSelected universes, provider adjustments, fractional modeling, unverified external exposure and unknown adaptive research remain. Live execution is disabled. Missing evidence is not a passed test.'),
        ('Conclusion', 'Researcher-written conclusion: not supplied. Automated calculations do not establish alpha or investment approval.\n\n' + block({'acceptance_criteria': thesis['acceptance_criteria'], 'rejection_criteria': thesis['rejection_criteria']})),
        ('References', '\n'.join(f"- {r['citation']} {r['url']} {r['doi']}" for r in project['references']) or 'No registered references.'),
        ('Appendix', block({'project_id': project['id'], 'revision_id': project['revision_id'], 'journal': project['journal']})),
    ]
    return '# ' + thesis['title'] + '\n\nArtifact-derived research draft. Authored thesis/notes and automated evidence are labeled separately.\n\n' + '\n\n'.join(f'## {i}. {title}\n\n{body}' for i, (title, body) in enumerate(sections, 1)) + '\n'


def export(service, project_id, packed=False):
    project = service.get(project_id, inspect=True)
    comparisons = [service.comparison(project_id, f['id']) for f in project['freezes']]
    text = markdown(project, comparisons)
    if not packed:
        return text
    files = {'report.md': text.encode(), 'project.json': json.dumps(project, indent=2).encode()}
    for trial in project['trials']:
        if not trial['evidence_id']:
            continue
        evidence = service.store.get(trial['evidence_id'], 'project_evidence')
        prefix = 'experiments/' + trial['id'] + '/'
        files[prefix + 'snapshot.json'] = json.dumps(evidence['snapshot']).encode()
        files[prefix + 'result.json'] = json.dumps(evidence['result'], indent=2).encode()
        files[prefix + 'prices.csv'] = evidence['snapshot']['prices_csv'].encode()
        files[prefix + 'benchmark.csv'] = evidence['snapshot']['benchmark_csv'].encode()
        files[prefix + 'source.zip'] = bytes.fromhex(service.store.get(evidence['source_id'], 'survival_source')['zip_hex'])
        for name, data in evidence['files'].items():
            files[prefix + name] = data.encode()
    for validation in project['validations']:
        inputs = service.store.get(validation['input_id'], 'survival_input')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('run.json', json.dumps({k: v for k, v in validation.items() if k != 'trial_id'}))
            archive.writestr('inputs.json', json.dumps(inputs))
            archive.writestr('source.zip', bytes.fromhex(service.store.get(validation['source_id'], 'survival_source')['zip_hex']))
            archive.writestr('trials.json', json.dumps([t for t in service.store.list('survival_trial') if t['run_id'] == validation['id'] or t['id'] in inputs['prior_trial_ids']]))
            archive.writestr('events.json', json.dumps(service.store.events(validation['id'])))
        files['validation/' + validation['id'] + '.zip'] = buffer.getvalue()
    # Sealed final bars must not leak through a pre-reveal export.
    revealed = {e['body']['dataset_id'] for e in project['journal'] if e['action'] == 'oos_revealed'}
    for dataset in project['datasets']:
        if dataset['id'] in revealed:
            body = service.store.get(dataset['id'], 'project_dataset')
            files['datasets/' + dataset['id'] + '.json'] = json.dumps(body).encode()
    for frozen in project['freezes']:
        files['versions/' + frozen['id'] + '.json'] = json.dumps(frozen, indent=2).encode()
    manifest = {'schema_version': 1, 'project_id': project_id, 'created_at': now(),
        'files': {name: digest(data) for name, data in files.items()},
        'replay': 'python -m research.projects.replay path/to/research-project.zip verifies the manifest, development targets/holdings/NAV, revealed OOS and completed Survival results. Requires the recorded source/dependencies; never executes archive code.',
        'sealed_holdout': 'Full dataset bars excluded until an explicit reveal; development experiments remain reproducible.'}
    files['manifest.json'] = json.dumps(manifest, indent=2).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    service.store.event(project_id, 'report_exported', {'manifest_hash': digest(manifest)})
    return output.getvalue()
