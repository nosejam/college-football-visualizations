"""Chronological, leak-free pregame Elo baseline; point-scale transfer is NOT SP+ validation."""
import gzip
import json
from pathlib import Path
import sys
import numpy as np
import pyarrow.parquet as pq
from scipy.optimize import minimize
from scipy.special import ndtr, expit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cfb.elo import update


def metrics(y,p):
    q=np.clip(p,1e-15,1-1e-15) # Numerical log protection only; not prediction clipping.
    bins=[]
    for lo in np.arange(0,1,.1):
        take=(p>=lo)&(p<(lo+.1 if lo<.9 else 1.0001))
        bins.append(dict(count=int(take.sum()),predicted=float(p[take].mean()) if take.any() else None,observed=float(y[take].mean()) if take.any() else None))
    return dict(n=len(y),brier=float(np.mean((p-y)**2)),log_loss=float(-np.mean(y*np.log(q)+(1-y)*np.log(1-q))),reliability=bins)


def build():
    games=json.loads(gzip.decompress((ROOT/'data/imperialism_games.json.gz').read_bytes()))
    rows=[]
    timeline=json.loads((ROOT/'data/imperialism.json').read_text())
    for season,items in sorted(games.items()):
        if int(season)>2025:continue
        ratings={}
        roster=set(timeline['seasons'][season]['roster'])
        sites={g['game_id']:bool(g.get('neutral_site')) for g in pq.read_table(ROOT/f'data/sources/imperialism/schedules_{season}.parquet').to_pylist()}
        for g in sorted(items,key=lambda g:(g['date'],g['game_id'])):
            a=ratings.get(g['home_id'],1500.);b=ratings.get(g['away_id'],1500.)
            margin=g['home_points']-g['away_points']
            # Train on FBS-v-FBS only; lower-division fallbacks are extrapolations.
            if g['home_id'] in roster and g['away_id'] in roster and margin:
                rows.append((int(season),a-b,0 if sites.get(g['game_id'],False) else 1,margin,int(margin>0)))
            ratings[g['home_id']],ratings[g['away_id']]=update(a,b,g['home_points'],g['away_points'])
    # Saved normalized games may expose FBS membership as a season roster instead.
    if not rows: raise ValueError('No FBS games available for calibration')
    x=np.array(rows,dtype=float);train=x[x[:,0]<=2022];valid=x[x[:,0]==2023];test=x[x[:,0]>=2024]
    design=train[:,1:3];coef=np.linalg.lstsq(design,train[:,3],rcond=None)[0]
    sigma=float(np.sqrt(np.mean((train[:,3]-design@coef)**2)))
    def loss(v):
        p=expit(design@v);return -np.mean(train[:,4]*np.log(np.maximum(p,1e-15))+(1-train[:,4])*np.log(np.maximum(1-p,1e-15)))
    logistic=minimize(loss,[.005,.2],method='BFGS').x
    def probabilities(z,kind):
        if kind=='normal':return ndtr((z[:,1:3]@coef)/sigma)
        if kind=='logistic':return expit(z[:,1:3]@logistic)
        return expit(z[:,1]*np.log(10)/400)
    validation={kind:metrics(valid[:,4],probabilities(valid,kind)) for kind in ['normal','logistic','legacy_elo']}
    chosen=min(['normal','logistic'],key=lambda k:validation[k]['log_loss'])
    report=dict(model_version='objective-sor-1',training_seasons=[2016,2022],validation_seasons=[2023],test_seasons=[2024,2025],training_games=len(train),
                margin=dict(elo_point_scale=float(coef[0]),home_field=float(coef[1]),sigma=sigma),
                logistic=dict(elo_slope=float(logistic[0]),home_logit=float(logistic[1])),selected=chosen,
                validation=validation,test={kind:metrics(test[:,4],probabilities(test,kind)) for kind in validation},
                sp_calibration='Unvalidated point-scale transfer from chronological pregame Elo residuals; no historical pregame SP+ snapshots available. Not an SP+ backtest.',
                source='Saved actual games; season-reset pregame Elo, never final-season ratings',probability_clip=None)
    folder=ROOT/'data/sources/ratings';folder.mkdir(exist_ok=True)
    (folder/'calibration.json').write_text(json.dumps(report,indent=2)+'\n')
    # Standalone reliability plot; matplotlib is an optional development dependency.
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(6,5));ax.plot([0,1],[0,1],'k--',label='Perfect calibration')
        for kind,entry in report['test'].items():
            bins=[b for b in entry['reliability'] if b['count']];ax.plot([b['predicted'] for b in bins],[b['observed'] for b in bins],'o-',label=kind)
        ax.set(xlabel='Predicted home win probability',ylabel='Observed home win frequency',title='Held-out 2024–2025 pregame Elo calibration',xlim=(0,1),ylim=(0,1));ax.legend();fig.tight_layout()
        fig.savefig(folder/'calibration.svg');plt.close(fig)
    except ImportError: print('Install matplotlib to regenerate calibration.svg')
    print(json.dumps({k:report[k] for k in ['training_games','margin','selected','sp_calibration']},indent=2))

if __name__=='__main__':build()
