"""Original native closed-cash model, admitted through Q's research queue."""
from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time
from uuid import uuid4
from typing import Annotated
import numpy as np

from pydantic import BaseModel, ConfigDict, Field, model_validator
from evidence.storage import digest

NATIVE = Path(__file__).parent / 'native'
SOURCES = {p.relative_to(NATIVE).as_posix(): p.read_text('utf-8')
           for p in sorted(NATIVE.rglob('*')) if p.suffix in {'.cpp', '.hpp', '.cu'}}
LIMITATIONS = [
    'SYNTHETIC closed-cash economy; households and firms are modeled agents, not observed companies or prices.',
    'Fixed prices and productivity, local markets, rotating employment and perishable output. No credit, banks, investment or asset market.',
    'Output is physical production, not GDP. Household wealth is cash. Saving is a cash flow, not investment.',
    'CUDA source is retained for reference. Q exposes the verified CPU path; no GPU speedup or financial-market phase is claimed.',
    'Timings are measured on this host; they are not performance guarantees or statistical evidence of economic realism.',
]


class EconomyConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    households: int = Field(10000, ge=1, le=1_000_000, strict=True)
    firms: int = Field(100, ge=1, le=10000, strict=True)
    steps: int = Field(100, ge=1, le=2000, strict=True)
    seed: int = Field(42, ge=0, le=2**32 - 1, strict=True)
    initial_wealth: float = Field(100, ge=0, le=1e9)
    firm_cash: float = Field(1000, ge=0, le=1e9)
    wage: float = Field(1, gt=0, le=1e9)
    price: float = Field(1, gt=0, le=1e9)
    productivity: float = Field(1.5, gt=0, le=1e9)
    propensity: float = Field(.08, ge=0, le=1)
    hiring_rate: float = Field(.85, ge=0, le=1)

    @model_validator(mode='after')
    def bounded(self):
        if self.firms > self.households:
            raise ValueError('Firms cannot exceed households')
        if self.households * self.steps > 20_000_000:
            raise ValueError('Limit each run to 20 million household timestep updates')
        return self


class BenchmarkConfig(EconomyConfig):
    populations: list[Annotated[int, Field(strict=True, ge=1, le=1_000_000)]] = Field(default_factory=lambda: [1000, 10000, 100000], min_length=1, max_length=6)
    repeats: int = Field(3, ge=2, le=5, strict=True)

    @model_validator(mode='after')
    def valid_populations(self):
        if len(set(self.populations)) != len(self.populations):
            raise ValueError('Benchmark populations must be unique')
        if any(type(n) is not int or not self.firms <= n <= 1_000_000 for n in self.populations):
            raise ValueError('Each population must be an integer between firms and one million')
        if sum(self.populations) * self.steps * (self.repeats + 1) > 60_000_000:
            raise ValueError('Limit a benchmark including warmups to 60 million updates')
        return self


def child_environment():
    # Native code and compilers need OS/runtime locations, never provider credentials.
    names = {'SYSTEMROOT', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP', 'COMSPEC',
             'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'HOME'}
    return {k: v for k, v in os.environ.items() if k.upper() in names}


def process(command, folder, cancel, timeout, env=None):
    with tempfile.TemporaryFile(mode='w+b') as log:
        child = subprocess.Popen(command, cwd=folder, env=env or child_environment(),
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        started = time.monotonic()
        try:
            while child.poll() is None:
                if cancel():
                    raise InterruptedError()
                if time.monotonic() - started > timeout:
                    raise ValueError('Native operation exceeded its time limit')
                time.sleep(.05)
            log.seek(0)
            output = log.read(64000).decode('utf-8', errors='replace')
            if child.returncode:
                raise ValueError('Native operation failed: ' + output[-1200:])
            return output
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)


def compile_native(folder, cancel=lambda: False, tests=False):
    if cancel():
        raise InterruptedError()
    spec = importlib.util.find_spec('ziglang')
    if spec is None:
        raise ValueError('Native compiler unavailable. Install Q requirements to enable the CPU economy.')
    zig = Path(spec.origin).parent / ('zig.exe' if os.name == 'nt' else 'zig')
    version = subprocess.run([str(zig), 'version'], capture_output=True, text=True,
                             timeout=10, check=True, env=child_environment()).stdout.strip()
    flags = ['-O3', '-std=c++17', '-ffp-contract=off']
    key = digest({'sources': SOURCES, 'compiler': version, 'flags': flags, 'platform': platform.platform()})
    build = Path(folder).resolve() / key
    build.mkdir(parents=True, exist_ok=True)
    binary = build / (('q-economy-tests' if tests else 'q-economy') + ('.exe' if os.name == 'nt' else ''))
    if not binary.is_file():
        for name, code in SOURCES.items():
            path = build / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(code, encoding='utf-8')
        pending = binary.with_name(binary.stem + '-pending' + binary.suffix)
        args = [str(zig), 'c++', *flags, '-I', str(build / 'simulation'),
                'simulation/cpu/economy.cpp', 'tests/test_engine.cpp' if tests else 'simulation/experiments/main.cpp',
                '-o', str(pending)]
        process(args, build, cancel, 240, {**child_environment(), 'ZIG_GLOBAL_CACHE_DIR': str(build / 'zig-cache')})
        pending.replace(binary)
    return binary, {'compiler': 'zig ' + version, 'flags': flags,
                    'binary_sha256': digest(binary.read_bytes()), 'source_hash': digest(SOURCES),
                    'platform': platform.platform(), 'device': 'cpu'}


def validate_output(config, result, rows):
    if result.get('device') != 'cpu' or len(rows) != config.steps:
        raise ValueError('Incomplete or unexpected native result')
    numbers = [v for row in rows for v in row.values()]
    numbers += [result[k] for k in ('initial_money', 'max_money_error', 'total_ms', 'throughput')]
    if not all(type(x) in (int, float) and math.isfinite(x) for x in numbers):
        raise ValueError('Non-finite native output')
    initial = result['initial_money']
    tolerance = 1e-8 + 1e-10 * abs(initial)
    previous_wealth = initial - config.firms * config.firm_cash
    residuals = []
    for step, row in enumerate(rows, 1):
        wealth = config.households * row['average_wealth']
        residual = abs(wealth + row['firm_cash'] - initial)
        if (row['step'] != step or residual > tolerance
                or abs(row['total_money'] - wealth - row['firm_cash']) > tolerance
                or abs(wealth - previous_wealth - row['savings']) > tolerance
                or min(wealth, row['firm_cash'], row['consumption'], row['output']) < -tolerance
                or not 0 <= row['employment'] <= config.households
                or not row['employment'].is_integer()
                or abs(row['unemployment'] - (1 - row['employment']/config.households)) > 1e-12
                or row['average_price'] != config.price
                or row['consumption'] > row['output'] * config.price + tolerance):
            raise ValueError('Native accounting invariant failed at step ' + str(step))
        residuals.append(residual)
        previous_wealth = wealth
    if result['max_money_error'] > tolerance:
        raise ValueError('Native cash conservation failed')
    if sum(row['count'] for row in result['wealth_histogram']) != config.households:
        raise ValueError('Native household histogram does not reconcile')
    return {'cash_conservation': True, 'saving_reconciliation': True,
            'max_reconstructed_money_error': max(residuals), 'tolerance': tolerance}


def run_native(config, binary, folder, cancel):
    with tempfile.TemporaryDirectory(prefix='economy-', dir=folder) as run_dir:
        command = [str(binary), '--output', run_dir, '--device', 'cpu']
        for key, value in config.model_dump().items():
            command += ['--' + key.replace('_', '-'), str(value)]
        process(command, run_dir, cancel, 90)
        result = json.loads((Path(run_dir) / 'result.json').read_text('utf-8'))
        with (Path(run_dir) / 'timeseries.csv').open() as stream:
            rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(stream)]
        checks = validate_output(config, result, rows)
        return {'native': result, 'series': rows, 'checks': checks}


def simulate(config, db, cancel=lambda: False, progress=lambda *_: None):
    folder = db.root / 'economy-build'
    binary, native_code = compile_native(folder, cancel)
    result = run_native(config, binary, folder, cancel)
    progress(1, 1)
    native = result['native']
    return {'name': 'SYNTHETIC native economy', 'synthetic': True, 'native_code': native_code,
            'checks': result['checks'], 'limitations': LIMITATIONS,
            'results': {'Economy': {'metrics': {k: native[k] for k in ('initial_money', 'max_money_error', 'total_ms', 'throughput')},
                                    'series': result['series'], 'household_cash': native['wealth_histogram'],
                                    'firms_first_256': native['firms']}},
            'charts': [{'section': 'Economy', 'table': 'series', 'x': 'step', 'keys': keys, 'label': label}
                       for keys, label in [(['output'], 'Physical production · synthetic units'),
                                           (['consumption', 'savings'], 'Consumption and net saving · cash units'),
                                           (['unemployment'], 'Unemployment fraction'),
                                           (['total_money', 'firm_cash'], 'Closed-system cash · total and firms')]]}


def benchmark(config, db, cancel=lambda: False, progress=lambda *_: None):
    folder = db.root / 'economy-build'
    binary, native_code = compile_native(folder, cancel)
    observations, summaries = [], []
    study_attempt_id = getattr(cancel, 'job_id', None) or uuid4().hex
    total = len(config.populations) * (config.repeats + 1)
    base = config.model_dump(exclude={'populations', 'repeats'})
    for population in config.populations:
        current = EconomyConfig(**{**base, 'households': population})
        timings = []
        for repeat in range(config.repeats + 1):
            if cancel():
                raise InterruptedError()
            result = run_native(current, binary, folder, cancel)
            ms = result['native']['total_ms']
            observation = {'population': population, 'repeat': repeat, 'warmup': repeat == 0,
                           'configuration': current.model_dump(), **result}
            # A later failure/cancellation must not discard completed measurements.
            from .service import freeze_request
            request = freeze_request(db, 'economy-simulation', current)
            observation_id = db.put('economy_observation', {
                'name': f'SYNTHETIC CPU observation · {population} households · {"warmup" if repeat == 0 else "repeat " + str(repeat)}',
                'synthetic': True, 'study_attempt_id': study_attempt_id, 'job_id': getattr(cancel, 'job_id', None), 'request': request,
                'native_code': native_code, **observation, 'limitations': LIMITATIONS})
            observations.append({'artifact_id': observation_id, **observation})
            if repeat:
                timings.append(ms)
            progress(len(observations), total)
        rng = np.random.default_rng(42)
        bootstrapped = np.median(rng.choice(timings, (10000, len(timings)), replace=True), axis=1)
        low, high = np.quantile(bootstrapped, [.025, .975])
        summaries.append({'population': population, 'median_ms': statistics.median(timings),
                          'ci95_low_ms': float(low), 'ci95_high_ms': float(high),
                          'min_ms': min(timings), 'max_ms': max(timings), 'repeats': config.repeats})
    return {'name': 'SYNTHETIC native CPU scaling study', 'synthetic': True, 'native_code': native_code,
            'bootstrap': {'seed': 42, 'resamples': 10000, 'interval': 'percentile 95% for median runtime'},
            'limitations': LIMITATIONS + ['Each population has one saved warmup excluded from medians. Fixed firm count changes the economic model as population changes.',
                                          'Bootstrap intervals describe measured timing variability, not economic uncertainty. Two to five repeats have poor interval resolution.'],
            'results': {'CPU scaling': {'measurements': summaries}}, 'attempts': observations,
            'charts': [{'section': 'CPU scaling', 'table': 'measurements', 'x': 'population',
                        'keys': ['median_ms'], 'label': 'Measured CPU runtime · milliseconds'}]}
