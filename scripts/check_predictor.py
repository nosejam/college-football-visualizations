"""Offline browser checks for playoff scenarios, records, sorting, probabilities, and tab state."""
import gzip
import json
import shutil
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def wait(frame):frame.wait_for_function('CFB_PLAYOFF?.ready&&!CFB_PLAYOFF.state.running',timeout=120000)
def choice(frame,team,mode):return frame.locator(f'tr[data-team="{team}"] input[data-mode="{mode}"]')

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('google-chrome') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1050},accept_downloads=True);errors=[];requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
    page.goto((ROOT/'index.html').as_uri()+'#predictor',wait_until='load')
    frame=page.query_selector('#view-predictor').content_frame();frame.select_option('#simulation-count','2000');wait(frame)
    assert page.get_by_role('tab').count()==3
    assert frame.locator('#prediction-rows tr').count()==138
    assert frame.locator('thead th').count()==21
    assert frame.evaluate('CFB_PLAYOFF.state.sort')=='objectiveRank'
    frame.select_option('#rating-method','elo');wait(frame)
    frame.click('[data-sort="elo"]')
    assert frame.evaluate('CFB_PLAYOFF.result.teams.reduce((n,t)=>n+t.playoffs,0)===12*CFB_PLAYOFF.result.iterations')
    assert frame.evaluate('CFB_PLAYOFF.result.teams.reduce((n,t)=>n+t.championships,0)===CFB_PLAYOFF.result.iterations')
    assert frame.evaluate('CFB_PLAYOFF.result.teams.reduce((n,t)=>n+t.conferenceWins,0)===10*CFB_PLAYOFF.result.iterations')
    assert frame.evaluate('CFB_PLAYOFF.result.teams.every(t=>!t.conferenceOut||t.conferenceWins===0)')
    assert frame.evaluate('''() => {const cells=[...document.querySelectorAll('#prediction-rows tr')].map(r=>Number(r.cells[20].textContent));return cells.every((v,i)=>!i||cells[i-1]>=v);}''')
    assert frame.locator('#week-slider').bounding_box()['y']<1050
    for key in ['conference','playoff','championship']:
        frame.click(f'[data-sort="{key}"]')
        assert frame.locator(f'th[data-column="{key}"]').get_attribute('aria-sort')=='descending'
        ids=frame.locator('#prediction-rows tr').evaluate_all('rows=>rows.map(r=>Number(r.dataset.team))')
        counts=frame.evaluate(f'Object.fromEntries(CFB_PLAYOFF.result.teams.map(t=>[t.id,t.{dict(conference="conferenceWins",playoff="playoffs",championship="championships")[key]}]))')
        assert all(counts[str(ids[i-1])]>=counts[str(ids[i])] for i in range(1,len(ids)))
    frame.click('[data-sort="elo"]')
    # Select a next-game matchup that is also the opponent's next game.
    pair=frame.evaluate('''() => {const d=CFB_PLAYOFF.data,s=CFB_PLAYOFF.state;for(const id of d.roster){const g=CFBPredictor.targets(d,s.index,id)[0];if(!g)continue;const other=g.home===id?g.away:g.home;if(d.roster.includes(other)&&CFBPredictor.targets(d,s.index,other)[0]?.id===g.id)return [id,other,g.id];}}''')
    assert pair;team,opponent,game=pair
    base=frame.evaluate('Object.fromEntries(CFB_PLAYOFF.result.teams.map(t=>[t.id,t.elo]))')
    choice(frame,team,'win-next').check();wait(frame)
    assert choice(frame,opponent,'lose-next').is_checked()
    assert not choice(frame,opponent,'win-next').is_checked()
    assert frame.evaluate(f'CFB_PLAYOFF.state.choices[{game}]')==team
    ratings=frame.evaluate('Object.fromEntries(CFB_PLAYOFF.result.teams.map(t=>[t.id,t.elo]))')
    assert ratings[str(team)]>base[str(team)] and ratings[str(opponent)]<base[str(opponent)]
    choice(frame,opponent,'win-next').check();wait(frame)
    assert choice(frame,team,'lose-next').is_checked()
    assert not choice(frame,team,'win-next').is_checked()
    assert frame.evaluate(f'CFB_PLAYOFF.state.choices[{game}]')==opponent
    assert 'replaced' in frame.locator('#scenario-note').inner_text()
    frame.click('#clear-scenario');wait(frame)
    choice(frame,team,'win-out').check();wait(frame)
    assert frame.evaluate(f'CFBPredictor.targets(CFB_PLAYOFF.data,CFB_PLAYOFF.state.index,{team}).every(g=>CFB_PLAYOFF.state.choices[g.id]==={team})')
    assert frame.locator('#scenario-summary').inner_text().startswith(str(frame.evaluate('Object.keys(CFB_PLAYOFF.state.choices).length')))
    page.click('#theme-toggle');frame.wait_for_function('document.documentElement.dataset.theme==="dark"')
    page.screenshot(path='/tmp/cfb-predictor-dark-scenario.png',full_page=True)
    page.click('#tab-circles');circles=page.query_selector('#view-circles').content_frame();circles.wait_for_function('CFB_CIRCLES?.ready')
    circles.click('#find-circles');circles.wait_for_function('CFB_CIRCLES.results&&!CFB_CIRCLES.state.searching')
    assert circles.evaluate('CFB_CIRCLES.state.which')=='smallest'
    assert circles.evaluate('CFB_CIRCLES.cycle.length===CFB_CIRCLES.results.shortest.length')
    # Cross-check the actual hover against all completed opponents, not just FBS graph edges.
    ident=circles.evaluate('CFB_CIRCLES.renderedNodes[0].id');year=circles.evaluate('CFB_CIRCLES.state.year');week=circles.evaluate('CFB_CIRCLES.data.seasons[CFB_CIRCLES.state.year].frames[CFB_CIRCLES.state.index].week')
    from cfb.imperialism import football_week
    raw=json.loads(gzip.decompress((ROOT/'data/imperialism_games.json.gz').read_bytes()))[str(year)];wins=losses=ties=0
    for g in raw:
        if football_week(year,g['date'])>week or ident not in [g['home_id'],g['away_id']]:continue
        side='home' if g['home_id']==ident else 'away';other='away' if side=='home' else 'home'
        wins+=g[side+'_points']>g[other+'_points'];losses+=g[side+'_points']<g[other+'_points'];ties+=g[side+'_points']==g[other+'_points']
    circles.locator('.team-node').first.hover()
    assert f'Record {wins}–{losses}'+(f'–{ties}' if ties else '') in circles.locator('#tooltip').inner_text()
    page.click('#tab-predictor');assert frame.evaluate(f'CFB_PLAYOFF.state.choices[{game}]')==team
    # Preseason gives everyone equal Elo, no observed records, and no hidden future scores.
    frame.locator('#week-slider').evaluate('el=>{el.value=0;el.dispatchEvent(new Event("input",{bubbles:true}));}');wait(frame)
    assert frame.evaluate('CFB_PLAYOFF.result.teams.every(t=>t.elo===1500)')
    assert frame.evaluate('Object.keys(CFB_PLAYOFF.state.choices).length')==0
    assert frame.evaluate('CFB_PLAYOFF.data.frames[0].records[130]')=={'wins':0,'losses':0,'ties':0}
    # Switching power source preserves scenarios; SP+ may explicitly fall back when unavailable.
    frame.select_option('#rating-method','sp');wait(frame)
    frame.locator('.team-name').first.click()
    assert 'SOR' in frame.locator('#resume-content').inner_text()
    assert frame.locator('#rating-status').inner_text()
    # Any zero without a mathematical proof is labeled rare rather than eliminated.
    assert frame.locator('.rare').evaluate_all('nodes=>nodes.every(n=>n.textContent.startsWith("~"))')
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(200)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert frame.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert frame.locator('.table-scroll').evaluate('el=>el.scrollWidth>el.clientWidth')
    page.screenshot(path='/tmp/cfb-predictor-mobile.png',full_page=True)
    assert not errors,errors
    assert not [r for r in requests if r.startswith(('http://','https://'))]
    browser.close()
    print('Passed: 138-team table, probability conservation, Elo/default and probability sorting, mirrored picks, conflict resolution, win-out scenarios, scenario Elo, theme, independent tabs, smallest-first cycles, record hover, preseason neutrality, rare-vs-eliminated labels, mobile table scrolling, and offline use.')
