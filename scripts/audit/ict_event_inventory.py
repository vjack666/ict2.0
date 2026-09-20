#!/usr/bin/env python3
"""Auditoría parcial, reproducible, de DETECTORES CANÓNICOS de ICT SYSTEM CLEAN.

Inputs: EURUSD.zip original, código recuperado de ZIP de CLEAN.
NO ejecuta MarketState/sequence/funnel/lifecycle. No es certificación de P1.
Registra ocurrencias de detectores por TF/tipo/confirmación; NO son episodios aceptados.
Recorta al instante T antes de invocar los detectores; no importa velas futuras.
"""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
import pandas as pd

TFS={'D1':'1D','H4':'4h','H1':'1h','M15':'15min','M5':'5min','M1':'1min'}
CONTROLS={'A':'2026-09-17T18:20:00Z','B':'2026-08-24T20:35:00Z'}
MEMBERS={tf:f"EURUSD/EURUSD_{'M5_3m' if tf=='M5' else tf}.csv" for tf in TFS}
WARMUP={'D1':'600D','H4':'120D','H1':'45D','M15':'21D','M5':'12D','M1':'12D'}


def read_source(z,tf,start):
    f=MEMBERS[tf]
    chunks=[]; total=0; last=None
    with z.open(f) as handle:
        for ch in pd.read_csv(handle,chunksize=120_000,usecols=lambda c:c in {'time','open','high','low','close','tick_volume'}):
            total+=len(ch)
            ts=pd.to_datetime(ch['time'],utc=True,errors='raise')
            if len(ts): last=ts.iloc[-1]
            sub=ch.loc[ts>=start].copy()
            if len(sub):
                sub['time']=ts[ts>=start].to_numpy()
                chunks.append(sub)
    if not chunks:
        return pd.DataFrame(columns=['time','open','high','low','close']),{'total_source_rows':total,'last_open':str(last)}
    d=pd.concat(chunks,ignore_index=True)
    d['time']=pd.to_datetime(d['time'],utc=True)
    d.sort_values('time',inplace=True);d.reset_index(drop=True,inplace=True)
    assert not d['time'].duplicated().any(),f'Duplicate time {tf}'
    assert not d[['open','high','low','close']].isna().any().any()
    assert (d['high']>=d[['open','low','close']].max(axis=1)).all()
    assert (d['low']<=d[['open','high','close']].min(axis=1)).all()
    return d,{'total_source_rows':total,'last_open':last.isoformat() if last is not None else None}


def extract(tf,closed,T,structure_fn,disp_fn,fvg_fn,ob_fn,lookback):
    """Run original detectors on closed-only, limited warmup historical context."""
    out=[]
    if len(closed)<25:return out,{'evaluated_bars':len(closed),'events_24h':0}
    d=closed.copy()
    # Source CSV 'time' denotes bar OPEN; engine expects bar CLOSE.
    d['time']=d['time']+pd.Timedelta(TFS[tf])
    assert (d['time']<=T).all()
    def add(kind,direction,bar_i,at,level=None,orig_id=None):
        t=pd.Timestamp(at)
        if t > T or t < T-pd.Timedelta('24h'):return
        e={'control':lookback,'tf':tf,'tipo':kind,'direccion':int(direction),
           'confirmation_time_utc':t.isoformat(),'bar_index_local':int(bar_i),
           'nivel':None if level is None or pd.isna(level) else float(level),
           'detector_object_id':orig_id}
        e['occurrence_id']=event_identity(tf,kind,t,direction)
        out.append(e)
    st=structure_fn(d).frame
    for i,row in st.loc[st['bos_dir']!=0].iterrows():
        add('BOS',row['bos_dir'],i,row['time'],row.get('bos_level'))
    for i,row in st.loc[st['choch_dir']!=0].iterrows():
        add('CHOCH',row['choch_dir'],i,row['time'],row.get('choch_proj_level'))
    for i,row in st.loc[st['mss_dir']!=0].iterrows():
        add('MSS',row['mss_dir'],i,row['time'])
    di=disp_fn(d)
    for kind,sign,col in [('DISPLACEMENT_BULL',1,'displacement_bullish'),('DISPLACEMENT_BEAR',-1,'displacement_bearish')]:
        for i,row in di.loc[di[col]].iterrows():
            add('DISPLACEMENT',sign,i,row['time'],row.get('close'))
    rows=d[['time','open','high','low','close']].to_dict('records')
    for ob in ob_fn(rows,timeframe=tf,symbol='EURUSD'):
        add('OB',ob.direction,ob.bar_index,ob.confirmation_time,ob.zone_low,orig_id=ob.id)
    for fv in fvg_fn(rows,timeframe=tf,symbol='EURUSD'):
        add('FVG',fv.direction,fv.bar_index,fv.confirmation_time,fv.zone_low,orig_id=fv.id)
    # No futuro: bos_real/quality/outcome are NOT published as as-of event attributes.
    # If no events, this is a valid detector observation, NOT accepted episode.
    return out,{'evaluated_bars':len(d),'event_rows_24h':len(out),
                'structure_bos_24h':sum(e['tipo']=='BOS' for e in out),
                'structure_choch_24h':sum(e['tipo']=='CHOCH' for e in out)}


def verify_sha256_manifest(z, manifest_path):
    """Compare physical source bytes against the selected manifest, not a printed prefix."""
    manifest=json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    selected={row['filename']:row['sha256'] for row in manifest['files']}
    hashes={}
    for tf,member in MEMBERS.items():
        filename=Path(member).name
        if filename not in selected:
            raise AssertionError(f'{filename}: not listed in manifest')
        digest=hashlib.sha256()
        with z.open(member) as f:
            for block in iter(lambda:f.read(1024*1024),b''):
                digest.update(block)
        observed=digest.hexdigest()
        if observed!=selected[filename]:
            raise AssertionError(f'{filename}: SHA256 differs from manifest')
        hashes[tf]={'filename':filename,'sha256':observed}
    if manifest.get('recent_window_source_selection',{}).get('M5',{}).get('selected')!='EURUSD_M5_3m.csv':
        raise AssertionError('recent M5 source in manifest is not M5_3m')
    return hashes


def event_identity(tf, kind, at, direction):
    """Identity of a detector occurrence, never a replay/poll timestamp."""
    if int(direction) not in (-1,1):
        raise ValueError('zero direction is not a new structure event')
    return f'{tf}|{kind}|{pd.Timestamp(at).isoformat()}|{int(direction)}'


def run(args):
    sys.path.insert(0,str(Path(args.clean_code).resolve()))
    from engine.bos.structure import detect_market_structure
    from detectors.displacement import detect_displacement
    from engine.detectors.fvg import detect_fvg
    from engine.detectors.ob import detect_order_blocks
    out_dir=Path(args.out);out_dir.mkdir(parents=True,exist_ok=True)
    result={'classification':'CANONICAL_DETECTOR_EVENTS_NOT_FUNNEL_EPISODES',
       'source_zip':str(args.source),'code_root':str(args.clean_code),
       'methods':['engine.bos.structure.detect_market_structure','detectors.displacement.detect_displacement',
                  'engine.detectors.fvg.detect_fvg','engine.detectors.ob.detect_order_blocks'],
       'event_count_semantics':'detector occurrences by (TF,family,confirmation_time,direction), not canonical MarketObject IDs or accepted episodes',
       'bar_time_assumption':'CSV time = OPEN; engine receives time=CLOSE (OPEN+TF); events counted only once per TF/type/direction/confirmation_time',
       'limitations':['NO reconstruye MarketState, secuencias, accepted episodes, lifecycle ni seis-TF pipeline completo',
                      'Historia limitada por ventana de warm-up; los eventos dependen del contexto inicial',
                      'D1/H4 cierres aproximados como OPEN+periodo fijo; requiere cotejo de calendario broker',
                      'NO es auditoria independiente ni FULL/PREFIX/Future Injection completos',
                      'No se publican bos_real/quality/outcome: pueden depender de velas posteriores al evento',
                      'M1 de CONTROL A OUT_OF_RANGE; M5 seleccionada M5_3m para ambas ventanas',
                      'No compara desempeño de trading; un FVG/OB detectado NO implica un setup elegible'],
       'controls':{}}
    all_events=[]
    start_time=time.perf_counter()
    with ZipFile(args.source) as z:
      result['verified_source_hashes']=verify_sha256_manifest(z,args.manifest)
      for tag,Tstr in CONTROLS.items():
        if args.control!='AB' and tag!=args.control: continue
        T=pd.Timestamp(Tstr)
        c={'decision_time':T.isoformat(),'frames':{},'families':{},'detector_occurrence_count_24h':0}
        for tf in TFS:
            if tag=='A' and tf=='M1':
                c['frames'][tf]={'status':'OUT_OF_RANGE','events_24h':0};continue
            start=T-pd.Timedelta(WARMUP[tf])
            d,meta=read_source(z,tf,start)
            # CLOSED-only immediately; discard bars in formation at T
            close=d['time']+pd.Timedelta(TFS[tf]);d=d.loc[close<=T].copy().reset_index(drop=True)
            if tf=='M1' and (not len(d) or pd.Timestamp(meta['last_open'])<T-pd.Timedelta('1h')):
                c['frames'][tf]={'status':'OUT_OF_RANGE','latest_source_open':meta['last_open']};continue
            if not len(d):
                c['frames'][tf]={'status':'NO_CLOSED_BARS','latest_source_open':meta['last_open']};continue
            e,debug=extract(tf,d,T,detect_market_structure,detect_displacement,detect_fvg,detect_order_blocks,tag)
            c['frames'][tf]={**meta,**debug,'status':'DETECTORS_EXECUTED',
             'first_used_open':d['time'].iloc[0].isoformat(),
             'last_used_open':d['time'].iloc[-1].isoformat(),
             'last_used_close':(d['time'].iloc[-1]+pd.Timedelta(TFS[tf])).isoformat()}
            all_events.extend(e)
            c['families'][tf]=dict(Counter(x['tipo'] for x in e))
            c['detector_occurrence_count_24h']+=len(e)
            print(tag,tf,'bars',len(d),'events last24h',len(e),'breakdown',c['families'][tf],flush=True)
        result['controls'][tag]=c
    df=pd.DataFrame(all_events)
    assert not df.duplicated(['control','occurrence_id']).any(),'duplicate detector occurrences within each control'
    # deduplicate cross-control events when the 24h windows do not overlap: none expected
    df.to_csv(out_dir/'eventos_detectores_canonicos_controles.csv',index=False)
    result['status']='DETECTOR_INVENTORY_ONLY_NOT_P1_PASS'
    result['elapsed_seconds']=round(time.perf_counter()-start_time,3)
    (out_dir/'resumen_detectores_canonicos.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True,help='ZIP original EURUSD con archivos EURUSD/EURUSD_*.csv');p.add_argument('--clean-code',type=Path,default=Path.cwd(),help='raíz del repositorio con engine/');p.add_argument('--manifest',type=Path,default=Path('benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json'));p.add_argument('--control',choices=['A','B','AB'],default='AB');p.add_argument('--out',type=Path,default=Path('reports/audits/experiments/temporal/detector_inventory'));a=p.parse_args();run(a)
