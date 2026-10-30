"""Immutable per-attempt usage ledger; costs are estimates, not invoices."""
import csv
from contextlib import closing
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

SCHEMA = '''CREATE TABLE IF NOT EXISTS requests (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT NOT NULL,
 mode TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
 attempt INTEGER NOT NULL, started_at TEXT NOT NULL, duration_ms INTEGER,
 gateway_request_id TEXT, status TEXT NOT NULL, error TEXT,
 prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER,
 cached_tokens INTEGER, reasoning_tokens INTEGER, tool_calls INTEGER,
 currency TEXT, estimated_cost TEXT, pricing_key TEXT, raw_usage TEXT
)'''

def init_db(path):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path)) as db:
        db.execute(SCHEMA)
        db.commit()
    return path

def record(path, **values):
    values.setdefault('id', str(uuid4()))
    values.setdefault('started_at', datetime.now(timezone.utc).isoformat())
    keys=list(values)
    with closing(sqlite3.connect(init_db(path))) as db:
        db.execute('INSERT INTO requests ('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')', [json.dumps(v,ensure_ascii=False) if k=='raw_usage' and v is not None else v for k,v in values.items()])
        db.commit()

def usage_fields(usage):
    if not usage: return dict(prompt_tokens=None,completion_tokens=None,total_tokens=None,cached_tokens=None,reasoning_tokens=None)
    d=usage if isinstance(usage,dict) else usage.model_dump(exclude_none=True)
    pd=d.get('prompt_tokens_details') or {}
    cd=d.get('completion_tokens_details') or {}
    return dict(prompt_tokens=d.get('prompt_tokens',d.get('input_tokens')),completion_tokens=d.get('completion_tokens',d.get('output_tokens')),total_tokens=d.get('total_tokens'),cached_tokens=d.get('prompt_cache_hit_tokens',pd.get('cached_tokens')) if d.get('prompt_cache_hit_tokens',pd.get('cached_tokens')) is not None else d.get('input_tokens_details',{}).get('cached_tokens'),reasoning_tokens=cd.get('reasoning_tokens') if cd.get('reasoning_tokens') is not None else d.get('output_tokens_details',{}).get('reasoning_tokens'))

def calculate_cost(u, prices):
    if not prices or u.get('prompt_tokens') is None or u.get('completion_tokens') is None: return None
    p=Decimal(str(u['prompt_tokens']))
    c=Decimal(str(u['completion_tokens']))
    h=u.get('cached_tokens')
    if h is None and 'cached_input_per_million' in prices: return None # cannot correctly split
    hit=Decimal(str(h or 0))
    if hit>p: return None
    cost=(p-hit)*Decimal(str(prices['input_per_million'])) + c*Decimal(str(prices['output_per_million']))
    if 'cached_input_per_million' in prices: cost+=hit*Decimal(str(prices['cached_input_per_million']))
    else: cost+=hit*Decimal(str(prices['input_per_million']))
    return str((cost/Decimal(1000000)).quantize(Decimal('0.00000001')))

def export_csv(path,destination):
    with closing(sqlite3.connect(init_db(path))) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('SELECT * FROM requests ORDER BY started_at,attempt').fetchall()
    with open(destination,'w',encoding='utf-8-sig',newline='') as out:
        writer=csv.writer(out)
        writer.writerow([d[0] for d in db_columns()])
        for row in rows:writer.writerow([row[d[0]] for d in db_columns()])
    return len(rows)

def db_columns():
    with closing(sqlite3.connect(':memory:')) as db:
        db.execute(SCHEMA)
        return db.execute('PRAGMA table_info(requests)').fetchall()

def summary(path):
    with closing(sqlite3.connect(init_db(path))) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('''SELECT provider,model,currency,COUNT(*) requests,
        SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) successes,
        SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) errors,
        SUM(prompt_tokens) input_tokens,SUM(completion_tokens) output_tokens,
        SUM(total_tokens) total_tokens, SUM(cached_tokens) cached_tokens,
        SUM(CAST(estimated_cost AS REAL)) estimated_cost,
        SUM(CASE WHEN estimated_cost IS NULL THEN 1 ELSE 0 END) unknown_cost_requests
        FROM requests GROUP BY provider,model,currency ORDER BY provider,model''').fetchall()
    return [dict(r) for r in rows]
