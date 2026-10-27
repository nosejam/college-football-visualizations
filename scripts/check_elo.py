"""Check Elo colors, time selection, scope stability, interaction, and SVG exports offline."""
import gzip
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]


def frame_index(frame,index):
    frame.locator('#week-slider').evaluate('(el,i)=>{el.value=i;el.dispatchEvent(new Event("input",{bubbles:true}));}',index)

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('google-chrome') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1600,'height':1050},accept_downloads=True,color_scheme='light')
    page=context.new_page();errors=[];requests=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda request:requests.append(request.url))
    page.goto((ROOT/'index.html').as_uri()+'#circles',wait_until='load')
    circles=page.query_selector('#view-circles').content_frame();circles.wait_for_function('CFB_CIRCLES?.ready')
    data=json.loads(gzip.decompress((ROOT/'data/team_elo.json.gz').read_bytes()))
    year=circles.evaluate('CFB_CIRCLES.state.year');saved=data['seasons'][str(year)]
    expected=dict(zip(saved['team_ids'],saved['frames'][-1]['ratings']))
    actual=circles.evaluate('Object.fromEntries(CFB_CIRCLES.renderedNodes.map(n=>[n.id,n.elo]))')
    assert all(value==expected[int(ident)] for ident,value in actual.items())
    assert circles.locator('.elo-ring').count()==138
    assert circles.evaluate('''() => {
      const nodes=CFB_CIRCLES.renderedNodes,lo=nodes.reduce((a,b)=>a.elo<b.elo?a:b),hi=nodes.reduce((a,b)=>a.elo>b.elo?a:b);
      return d3.color(lo.eloColor).formatHex()==='#df4a48' && d3.color(hi.eloColor).formatHex()==='#2eae63';
    }''')
    # Focus/cycle filters leave a team's rating and scale unchanged.
    before=circles.evaluate('({range:CFB_CIRCLES.eloRange,colors:Object.fromEntries(CFB_CIRCLES.renderedNodes.map(n=>[n.id,n.eloColor]))})')
    circles.select_option('#team-select','130');circles.click('#find-circles')
    circles.wait_for_function('CFB_CIRCLES.results&&!CFB_CIRCLES.state.searching')
    assert circles.evaluate('CFB_CIRCLES.cycle?.includes(130)')
    assert circles.evaluate('CFB_CIRCLES.eloRange')==before['range']
    for node in circles.evaluate('CFB_CIRCLES.renderedNodes.map(n=>({id:n.id,color:n.eloColor,elo:n.elo}))'):
        assert node['color']==before['colors'][str(node['id'])]
        assert node['elo']==expected[node['id']]
    # Selection/hover must never replace the colored Elo ring with the selection color.
    focused=circles.locator('.team-node.focused').first
    ring=focused.locator('.elo-ring');fill=ring.get_attribute('fill')
    focused.hover();assert ring.get_attribute('fill')==fill
    assert ring.evaluate('el=>getComputedStyle(el).stroke')=='none'
    assert 'Elo ' in circles.locator('#tooltip').inner_text()
    assert 'Elo after game:' in circles.locator('#evidence-list').inner_text()
    assert circles.evaluate('CFB_CIRCLES.renderedNodes.every(n=>document.querySelector(`.team-node[aria-label^="${n.school}."]`)?.getAttribute("aria-label").includes("Elo"))')
    page.screenshot(path='/tmp/cfb-elo-light-circle.png',full_page=True)
    page.click('#theme-toggle');circles.wait_for_function('document.documentElement.dataset.theme==="dark"')
    assert ring.get_attribute('fill')==fill
    page.screenshot(path='/tmp/cfb-elo-dark-circle.png',full_page=True)
    with page.expect_download() as info:circles.click('#export')
    info.value.save_as('/tmp/cfb-elo.svg')
    root=ET.parse('/tmp/cfb-elo.svg').getroot();ns={'s':'http://www.w3.org/2000/svg'}
    rings=root.findall('.//s:circle[@class="elo-ring"]',ns)
    assert len(rings)==circles.locator('.elo-ring').count()
    assert all(r.get('data-elo') and r.get('fill')!='none' for r in rings)
    assert 'Elo rings:' in ''.join(root.itertext())
    # Preseason is uniformly 1500/amber; earlier weeks cannot use latest-season ratings.
    frame_index(circles,0)
    assert circles.evaluate('CFB_CIRCLES.renderedNodes.every(n=>n.elo===1500&&n.eloColor==="#efc65b")')
    assert 'All teams tied' in circles.locator('#elo-scope').inner_text()
    frame_index(circles,1)
    early=dict(zip(saved['team_ids'],saved['frames'][1]['ratings']))
    assert all(node['elo']==early[node['id']] for node in circles.evaluate('CFB_CIRCLES.renderedNodes.map(n=>({id:n.id,elo:n.elo}))'))
    circles.select_option('#scope-select','opponents')
    assert circles.evaluate('CFB_CIRCLES.renderedNodes.every(n=>Number.isFinite(n.elo))')
    circles.select_option('#season-select','2016')
    assert circles.evaluate('CFB_CIRCLES.renderedNodes.every(n=>n.elo===1500)')
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(300)
    assert circles.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    assert not [url for url in requests if url.startswith(('http://','https://'))]
    browser.close()
    print('Passed: saved Elo parameters, red/green endpoints, stable colors through filtering, selected/hover rings, numeric tooltips and evidence, both themes, SVG rings/legend, preseason reset, earlier-week isolation, opponent scope, mobile, and offline use.')
