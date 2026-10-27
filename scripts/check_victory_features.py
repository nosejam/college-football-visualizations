"""Browser regressions for shared themes, cycle catalogs, multi-team search, and fallback paths."""
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BROWSER=shutil.which('google-chrome') or shutil.which('chromium')
assert BROWSER,'Install Chrome/Chromium to run browser checks'

def wait_search(frame):
    frame.wait_for_function('CFB_CIRCLES.results && !CFB_CIRCLES.state.searching',timeout=20000)

def week(frame,number):
    frame.locator('#week-slider').evaluate('''(el,week)=>{
      el.value=CFB_CIRCLES_DATA.seasons[CFB_CIRCLES.state.year].frames.findIndex(f=>f.week===week);
      el.dispatchEvent(new Event('input',{bubbles:true}));
    }''',number)

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=BROWSER,headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1600,'height':1050},color_scheme='dark',accept_downloads=True)
    page=context.new_page();errors=[];requests=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda request:requests.append(request.url))
    page.goto((ROOT/'index.html').as_uri()+'#imperialism',wait_until='load')
    assert page.get_by_role('tab',name='Victory Cycles').count()==1
    assert page.locator('html').get_attribute('data-theme')=='dark'
    imperialism=page.query_selector('#view-imperialism').content_frame()
    imperialism.wait_for_function('CFB_IMPERIALISM?.ready && !CFB_IMPERIALISM.rendering')
    assert imperialism.evaluate('document.getElementById("map")._fullLayout.paper_bgcolor')=='#111b24'
    imperialism.click('#zoom-in');imperialism.wait_for_timeout(200)
    scale=imperialism.evaluate('document.getElementById("map")._fullLayout.geo.projection.scale')
    page.click('#theme-toggle')
    imperialism.wait_for_function('document.getElementById("map")._fullLayout.paper_bgcolor==="#f6f5f0"')
    assert imperialism.evaluate('document.getElementById("map")._fullLayout.geo.projection.scale')==scale
    page.click('#tab-circles')
    circles=page.query_selector('#view-circles').content_frame()
    circles.wait_for_function('CFB_CIRCLES?.ready')
    assert circles.locator('html').get_attribute('data-theme')=='light'
    page.click('#theme-toggle');circles.wait_for_function('document.documentElement.dataset.theme==="dark"')
    # A large graph is bounded and lists five long/five short discoveries, rather than claiming every cycle.
    circles.click('#find-circles');wait_search(circles)
    assert circles.evaluate('CFB_CIRCLES.results.collapsed')
    assert 5<=circles.locator('.cycle-option').count()<=10
    assert 'found' in circles.locator('#catalog-summary').inner_text()
    assert circles.evaluate('CFB_CIRCLES.results.cycles.every(c=>CFBCycles.valid(c,CFBCycles.graph(CFB_CIRCLES.nodes,CFB_CIRCLES.edges),2))')
    circles.locator('.cycle-option').last.click()
    assert circles.locator('.cycle-option[aria-pressed=true]').count()==1
    assert circles.evaluate('CFB_CIRCLES.cycle.length')==circles.locator('#evidence-list .evidence-row').count()
    page.screenshot(path='/tmp/victory-dark-catalog.png',full_page=True)
    with page.expect_download() as info:circles.click('#export')
    info.value.save_as('/tmp/victory-dark.svg')
    export=Path('/tmp/victory-dark.svg').read_text();assert '#111b24' in export and '#e6eef2' in export
    circles.click('#back-network');week(circles,6)
    for ident in ['130','201','251']:circles.select_option('#team-select',ident)
    assert circles.locator('.team-chip').count()==3
    assert 'every selected' in circles.locator('#require-label').inner_text()
    circles.click('#find-circles');wait_search(circles)
    assert circles.evaluate('CFB_CIRCLES.results.cycles.length>0 && CFB_CIRCLES.results.cycles.every(c=>[130,201,251].every(id=>c.includes(id)))')
    circles.fill('#circle-length','5');circles.click('#find-length');wait_search(circles)
    assert circles.evaluate('CFB_CIRCLES.results.cycles.every(c=>[130,201,251].every(id=>c.includes(id)))')
    assert circles.evaluate('CFB_CIRCLES.cycle')==[130,201,251,194,2294]
    circles.get_by_role('button',name='Remove Oklahoma',exact=True).click()
    assert circles.evaluate('CFB_CIRCLES.state.selected')==[130,251]
    page.screenshot(path='/tmp/victory-dark-selection.png',full_page=True)
    circles.click('#clear-focus');week(circles,2)
    # Choose real teams with an undirected played-game path but in distinct SCCs: no common directed cycle exists.
    pair=circles.evaluate('''() => {
      const f=CFB_CIRCLES.state.full,g=CFBCycles.graph(f.nodes,f.edges),parts=CFBCycles.components(g),part=new Map(parts.flatMap((p,i)=>p.map(id=>[id,i])));
      for(const a of f.nodes)for(const b of f.nodes)if(a<b&&part.get(a)!==part.get(b)){
        const link=CFBCycles.connection(f.nodes,f.edges,[a,b]);
        if(link.connected&&link.paths[0]?.length>=3)return [a,b];
      }
    }''')
    assert pair
    circles.select_option('#team-select',str(pair[0]));circles.click('#find-circles');wait_search(circles)
    assert circles.evaluate('CFB_CIRCLES.view')=='fallback'
    assert circles.evaluate('''() => {
      const s=CFB_CIRCLES.state,expected=CFBCycles.neighborhood(s.full.nodes,s.full.edges,s.selected[0],1).nodes;
      return expected.length===CFB_CIRCLES.renderedNodes.length && CFB_CIRCLES.renderedNodes.every(n=>expected.includes(n.id));
    }''')
    circles.select_option('#team-select',str(pair[1]));circles.click('#find-circles');wait_search(circles)
    assert circles.evaluate('CFB_CIRCLES.view==="fallback" && CFB_CIRCLES.fallback.connected')
    assert circles.evaluate('CFB_CIRCLES.renderedNodes.length===CFB_CIRCLES.fallback.paths[0].length')
    assert circles.evaluate('CFB_CIRCLES.renderedEdges.every(e=>e.games.every(g=>g.winner===e.source.id&&g.loser===e.target.id))')
    assert 'shortest played-game' in circles.locator('#search-status').inner_text()
    page.screenshot(path='/tmp/victory-dark-path.png',full_page=True)
    # Disconnected preseason selections have no invented connecting edge.
    week(circles,None);circles.click('#find-circles');wait_search(circles)
    assert circles.evaluate('CFB_CIRCLES.view==="fallback" && !CFB_CIRCLES.fallback.connected && CFB_CIRCLES.renderedEdges.length===0')
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(300)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert circles.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path='/tmp/victory-dark-mobile.png',full_page=True)
    page.reload(wait_until='load');assert page.locator('html').get_attribute('data-theme')=='dark'
    assert page.locator('#theme-toggle').get_attribute('aria-checked')=='true'
    assert not errors,errors
    assert not [url for url in requests if url.startswith(('http://','https://'))]
    browser.close()
    print('Passed: device theme, saved theme, lazy views, live Plotly colors without resetting zoom, dark SVG export, bounded selectable catalogs, required-team intersection, chip removal, single-team fallback, shortest played-game path and real arrow directions, disconnected selections, mobile, and offline use.')
