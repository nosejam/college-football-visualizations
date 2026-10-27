"""Rebuild the offline app from saved inputs, without downloading anything."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-closest-map',action='store_true',help='Also regenerate the original closest-campus standalone map and geography')
    args=parser.parse_args()
    steps=[]
    if args.include_closest_map:
        steps.append('build_geography.py')
    steps+=['build_imperialism.py','build_elo.py','compute_circles.py','build_circles.py','build_predictor.py','build_visualizations.py']
    for script in steps:
        subprocess.run([sys.executable,str(ROOT/'scripts'/script)],cwd=ROOT,check=True)

if __name__=='__main__':main()
