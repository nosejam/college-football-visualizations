"""Exercise the actual standalone circles explorer in Chrome/Chromium."""
import argparse
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--browser',default=shutil.which('google-chrome') or shutil.which('chromium'));args=parser.parse_args()
if not args.browser:parser.error('Pass --browser /path/to/chrome')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1050},device_scale_factor=1,accept_downloads=True)
    errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
    page.goto((ROOT/'build/circles-of-suck.html').as_uri(),wait_until='load');page.wait_for_function('window.CFB_CIRCLES?.ready',timeout=30000)
    assert page.locator('#season-select option').count()==11
    assert page.locator('#include-pairs').is_checked()
    assert page.evaluate('CFB_CIRCLES.state.year')==2026
    assert page.evaluate('CFB_CIRCLES.nodes.length')==138
    # Keep the historical Week 7 regression stable as newer results arrive.
    page.locator('#week-slider').evaluate('el=>{el.value=CFB_CIRCLES_DATA.seasons[2026].frames.findIndex(f=>f.week===7);el.dispatchEvent(new Event("input",{bubbles:true}));}')
    assert page.evaluate('CFB_CIRCLES.edges.every(e=>e.games.every(g=>g.week<=7))')
    assert page.evaluate('CFB_CIRCLES.edges.every(e=>e.games.every(g=>g.winner===e.source&&g.loser===e.target&&g.winner_points>g.loser_points))')
    page.screenshot(path='/tmp/circles-network-final.png',full_page=True)
    # Actual logo clicks focus the selected school and keyboard activation can refocus.
    page.locator('.team-node[aria-label^="Alabama."]').click()
    assert page.evaluate('CFB_CIRCLES.state.root')==333
    assert page.evaluate('CFB_CIRCLES.state.depth===Infinity && CFB_CIRCLES.nodes.length===CFB_CIRCLES.state.visible.componentSize')
    page.click('#direct-hops')
    direct=page.evaluate('CFB_CIRCLES.nodes.length');assert 1<direct<138
    assert page.evaluate('CFB_CIRCLES.edges.every(e=>CFB_CIRCLES.nodes.includes(e.source)&&CFB_CIRCLES.nodes.includes(e.target))')
    page.click('#more-hops');assert page.evaluate('CFB_CIRCLES.nodes.length')>direct
    assert page.evaluate('CFB_CIRCLES.state.depth')==2
    page.screenshot(path='/tmp/circles-neighborhood-final.png',full_page=True)
    page.click('#find-circles');page.wait_for_function('CFB_CIRCLES.results && !CFB_CIRCLES.state.searching',timeout=15000)
    assert page.evaluate('CFB_CIRCLES.results.largest.length===0||CFB_CIRCLES.results.largest.includes(333)')
    assert page.evaluate('CFB_CIRCLES.results.shortest.length===0||CFB_CIRCLES.results.shortest.includes(333)')
    page.click('#clear-focus');assert page.evaluate('CFB_CIRCLES.nodes.length')==138
    page.click('#find-circles');page.wait_for_function('CFB_CIRCLES.results && !CFB_CIRCLES.state.searching')
    assert page.evaluate('CFB_CIRCLES.results.shortest.length')==3
    assert page.evaluate('CFB_CIRCLES.state.which')=='smallest'
    assert page.evaluate('CFB_CIRCLES.cycle.length')==3
    page.click('#largest')
    assert page.evaluate('CFB_CIRCLES.results.largest.length')==61
    assert page.evaluate('CFB_CIRCLES.results.exact')
    assert page.locator('#evidence-list .evidence-row').count()==61
    assert page.evaluate('CFB_CIRCLES.renderedEdges.length===61 && CFBCycles.valid(CFB_CIRCLES.results.largest,CFBCycles.graph(CFB_CIRCLES.nodes,CFB_CIRCLES.edges))')
    assert page.evaluate('''CFB_CIRCLES.renderedEdges.every(e=>{
      const p=document.querySelectorAll('.edge')[CFB_CIRCLES.renderedEdges.indexOf(e)];
      const a=p.getPointAtLength(0),b=p.getPointAtLength(p.getTotalLength());
      return (b.x-a.x)*(e.target.x-e.source.x)+(b.y-a.y)*(e.target.y-e.source.y)>0;
    })''')
    page.screenshot(path='/tmp/circles-largest-final.png',full_page=True)
    page.click('#smallest');assert page.locator('.team-node').count()==3
    assert page.locator('#evidence-list .evidence-row').count()==3
    assert page.locator('.edge[marker-end="url(#circle-arrow)"]').count()==3
    page.screenshot(path='/tmp/circles-smallest-final.png',full_page=True)
    page.check('#show-names');assert page.locator('.node-name').first.get_attribute('display')=='inline'
    with page.expect_download() as info:page.click('#export')
    info.value.save_as('/tmp/circles-check.svg');export=Path('/tmp/circles-check.svg').read_text()
    assert '<image' in export and 'marker-end' in export and '2026' in export and 'Proven smallest' in export
    page.click('#back-network');assert page.locator('.team-node').count()==138
    page.select_option('#scope-select','opponents');assert page.evaluate('CFB_CIRCLES.nodes.length')>138
    page.click('#find-circles');page.wait_for_function('CFB_CIRCLES.results && !CFB_CIRCLES.state.searching',timeout=15000)
    assert page.evaluate('CFBCycles.valid(CFB_CIRCLES.results.largest,CFBCycles.graph(CFB_CIRCLES.nodes,CFB_CIRCLES.edges))')
    if not page.evaluate('CFB_CIRCLES.results.exact'):
        assert 'Best found' in page.locator('#largest-proof').inner_text()
        assert page.locator('#search-longer').is_visible()
        page.click('#search-longer');page.wait_for_timeout(100)
    # Changing the week cancels any running worker, including extended searches.
    page.locator('#week-slider').evaluate('(el)=>{el.value=0;el.dispatchEvent(new Event("input",{bubbles:true}));}')
    assert page.evaluate('!CFB_CIRCLES.state.searching && CFB_CIRCLES.state.results===null && CFB_CIRCLES.edges.length===0')
    page.wait_for_timeout(500);assert page.locator('#smallest-size').inner_text()=='—'
    assert page.locator('#graph-notice').is_visible();assert page.locator('#find-circles').is_disabled()
    page.select_option('#scope-select','fbs')
    for year in range(2016,2027):
        page.select_option('#season-select',str(year));assert page.evaluate('CFB_CIRCLES.state.index')==0
        final=page.evaluate('CFB_CIRCLES_DATA.seasons[CFB_CIRCLES.state.year].frames.length-1')
        page.locator('#week-slider').evaluate('(el,v)=>{el.value=v;el.dispatchEvent(new Event("input",{bubbles:true}));}',final)
        assert page.evaluate('CFB_CIRCLES.edges.every(e=>e.games.every(g=>g.week<=CFB_CIRCLES_DATA.seasons[CFB_CIRCLES.state.year].frames[CFB_CIRCLES.state.index].week))')
    # The user's five-team example is present by 2026 Week 6, not before its last win.
    page.select_option('#team-select','130')
    week6=page.evaluate('CFB_CIRCLES_DATA.seasons[2026].frames.findIndex(f=>f.week===6)')
    page.locator('#week-slider').evaluate('(el,v)=>{el.value=v;el.dispatchEvent(new Event("input",{bubbles:true}));}',week6)
    page.fill('#circle-length','5');page.click('#find-length')
    page.wait_for_function('CFB_CIRCLES.results?.mode==="length" && !CFB_CIRCLES.state.searching')
    assert page.evaluate('CFB_CIRCLES.cycle')==[130,201,251,194,2294]
    assert page.locator('.team-node').count()==5
    assert page.locator('#evidence-list .evidence-row').count()==5
    assert '27–24' in page.locator('#evidence-list').inner_text()
    assert 'Every win verified' in page.locator('#network').text_content()
    page.screenshot(path='/tmp/circles-michigan-five-final.png',full_page=True)
    page.locator('#week-slider').evaluate('(el,v)=>{el.value=v-1;el.dispatchEvent(new Event("input",{bubbles:true}));}',week6)
    page.click('#find-length');page.wait_for_function('CFB_CIRCLES.results?.mode==="length" && !CFB_CIRCLES.state.searching')
    assert page.evaluate('!CFB_CIRCLES.results.cycles.some(c=>CFBCycles.canonical(c).join(":")==="130:201:251:194:2294")')
    page.locator('#week-slider').evaluate('(el,v)=>{el.value=v;el.dispatchEvent(new Event("input",{bubbles:true}));}',week6)
    page.click('#clear-focus');page.click('#find-length');page.wait_for_function('CFB_CIRCLES.results?.mode==="length" && !CFB_CIRCLES.state.searching')
    assert page.evaluate('CFB_CIRCLES.results.cycles.length')>1
    first=page.evaluate('CFB_CIRCLES.cycle');page.click('#next-circle');assert page.evaluate('CFB_CIRCLES.cycle')!=first
    assert page.locator('.team-node').count()==5
    # Extremes remain available after an exact-size result.
    page.click('#find-circles');page.wait_for_function('CFB_CIRCLES.results && CFB_CIRCLES.results.mode!=="length" && !CFB_CIRCLES.state.searching')
    assert page.evaluate('CFB_CIRCLES.results.exact')
    # Use a season with rematches to verify the optional pair rule.
    page.select_option('#season-select','2025')
    final=page.evaluate('CFB_CIRCLES_DATA.seasons[2025].frames.length-1')
    page.locator('#week-slider').evaluate('(el,v)=>{el.value=v;el.dispatchEvent(new Event("input",{bubbles:true}));}',final)
    page.check('#include-pairs');page.click('#find-circles');page.wait_for_function('CFB_CIRCLES.results && !CFB_CIRCLES.state.searching')
    assert page.evaluate('CFB_CIRCLES.results.shortest.length')==2
    page.click('#smallest');assert page.locator('.team-node').count()==2
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(300)
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    page.screenshot(path='/tmp/circles-mobile-final.png',full_page=True)
    assert not errors,errors
    assert not [r for r in requests if r.startswith('http')]
    print('Passed: 11 seasons, cumulative weeks, winner-to-loser arrows, logo focus, hop expansion, scoped cycles, exact full-FBS extrema, exact-size searches, the Michigan example, browsing matches, proof games, rematches, worker cancellation, SVG export, mobile, and offline use.')
    browser.close()
