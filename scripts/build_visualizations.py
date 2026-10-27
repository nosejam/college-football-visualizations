"""Bundle the standalone visualizations into one offline tabbed document."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

EMBED_STYLE='''<style>
body.predictor-page>header{display:none!important}html{scrollbar-gutter:stable}header{padding:13px 24px!important;align-items:center!important;flex-direction:row!important;gap:18px!important}header .eyebrow,header h1{display:none!important}header p{font-size:12px!important;margin:0!important}header>div:first-child{min-width:0}.season-control{min-width:125px!important;width:auto!important;display:block!important}.season-control select{margin-top:5px!important;width:125px!important}.season-control .label{font-size:9px!important}footer{padding:12px 24px 18px!important}nav[aria-label="Visualizations"]{display:none!important}@media(min-width:951px){.sidebar{max-height:calc(100vh - 190px)}}@media(max-width:520px){header{padding:12px 15px!important;gap:12px!important}header p{font-size:11px!important}.season-control{min-width:100px!important}.season-control select{width:100px!important}}
</style>'''


def build():
    views={}
    for name,file in [('imperialism','build/imperialism.html'),('circles','build/circles-of-suck.html'),('predictor','build/playoff-predictor.html')]:
        source=(ROOT/file).read_text()
        assert '<!doctype html>' in source.lower(),f'Build {file} first'
        views[name]=source.replace('</head>',EMBED_STYLE+'\n</head>',1)
    template=(ROOT/'maps/visualizations-template.html').read_text()
    payload=json.dumps(views,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    output=template.replace('__VIEWS__',payload).replace('__APP_JS__',(ROOT/'maps/visualizations.js').read_text())
    output=output.replace('__THEME_CSS__',(ROOT/'maps/theme.css').read_text()).replace('__THEME_JS__',(ROOT/'maps/theme.js').read_text())
    path=ROOT/'index.html';path.write_text(output)
    print(f'Built index.html ({path.stat().st_size/1024/1024:.1f} MiB): Imperialism Map + Victory Cycles + Playoff Predictor, offline.')

if __name__=='__main__':build()
