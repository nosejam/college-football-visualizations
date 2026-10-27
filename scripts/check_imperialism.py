"""Check imperialism playback in a real offline browser (requires Playwright + Chrome)."""
import argparse
import json
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--browser',default=shutil.which('google-chrome') or shutil.which('chromium'))
args=parser.parse_args()
if not args.browser:parser.error('Pass --browser /path/to/chrome')

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1050},device_scale_factor=1,accept_downloads=True)
    errors=[];requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:requests.append(r.url))
    page.goto((ROOT/'build/imperialism.html').as_uri(),wait_until='load')
    page.wait_for_function('window.CFB_IMPERIALISM?.ready===true && !CFB_IMPERIALISM.rendering',timeout=45000)
    assert page.locator('#season-select option').count()==11
    assert page.evaluate('CFB_IMPERIALISM.season')==2026
    assert page.evaluate('CFB_IMPERIALISM.frame.week===CFB_IMPERIALISM_DATA.seasons[2026].frames.at(-1).week')
    assert page.evaluate('CFB_IMPERIALISM.countyOwners.length')==3144
    assert page.locator('#week-slider').evaluate('(el)=>el.closest(".map-column").contains(document.getElementById("map"))')
    def check_containment():
        return page.evaluate('''() => {
          const projection=document.getElementById('map')._fullLayout.geo._subplot.projection;
          const result=[];
          for(const m of CFB_IMPERIALISM.logoMetrics) {
            const path=document.createElementNS('http://www.w3.org/2000/svg','path');
            path.setAttribute('d',d3.geoPath(projection)(CFB_IMPERIALISM.geography.regions.get(m.seed)));
            document.getElementById('logo-overlay').appendChild(path);
            for(const x of [-.5,0,.5])for(const y of [-.5,0,.5]) {
              if(!path.isPointInFill(new DOMPoint(m.center[0]+x*m.size,m.center[1]+y*m.size)))result.push({seed:m.seed,part:m.part,x,y});
            }
            path.remove();
          }
          return result;
        }''')
    failures=check_containment();print('Logo containment failures:',failures);assert not failures
    page.screenshot(path='/tmp/imperialism-desktop.png',full_page=True)
    def choose_year(year):
        page.select_option('#season-select',str(year))
        page.wait_for_function('(year)=>!CFB_IMPERIALISM.rendering && CFB_IMPERIALISM.season===year && CFB_IMPERIALISM.frameIndex===0',arg=year)
        assert page.locator('#week-slider').input_value()=='0'
    def choose_index(index):
        page.locator('#week-slider').evaluate('(el,index)=>{el.value=index;el.dispatchEvent(new Event("input",{bubbles:true}));}',index)
        page.wait_for_function('(index)=>!CFB_IMPERIALISM.rendering && CFB_IMPERIALISM.frameIndex===index',arg=index)
    def choose_week(week):
        index=page.evaluate('(week)=>CFB_IMPERIALISM_DATA.seasons[CFB_IMPERIALISM.season].frames.findIndex(f=>f.week===week)',week)
        assert index>=0;choose_index(index)
    choose_year(2016)
    assert page.evaluate('CFB_IMPERIALISM.frame.week') is None
    assert page.evaluate('CFB_IMPERIALISM.owners[2294]')==2294
    choose_week(3);assert page.evaluate('CFB_IMPERIALISM.owners[2294]')==2449
    choose_week(7);assert page.evaluate('CFB_IMPERIALISM.owners[2294]')==2571
    final=page.evaluate('CFB_IMPERIALISM_DATA.seasons[2016].frames.length-1');choose_index(final)
    assert page.evaluate('CFB_IMPERIALISM.owners[2294]')==256
    page.select_option('#team-select','2294');assert 'No land' in page.locator('#team-detail').inner_text()
    # Rapid input events must settle on the latest requested position.
    page.locator('#week-slider').evaluate('(el)=>{for(const n of [2,5,10,3,0]){el.value=n;el.dispatchEvent(new Event("input",{bubbles:true}));}}')
    page.wait_for_function('!CFB_IMPERIALISM.rendering && CFB_IMPERIALISM.frameIndex===0')
    for year in range(2017,2027):
        choose_year(year)
        final=page.evaluate('(year)=>CFB_IMPERIALISM_DATA.seasons[year].frames.length-1',year)
        choose_index(final)
        assert page.evaluate('CFB_IMPERIALISM.countyOwners.length')==3144
        assert int(page.locator('#week-slider').get_attribute('max'))==final
    # Change season/slider while a previous Plotly update is still pending.
    page.evaluate('''() => {
      const year=document.getElementById('season-select'),slider=document.getElementById('week-slider');
      year.value=2020;year.dispatchEvent(new Event('change',{bubbles:true}));
      slider.value=20;slider.dispatchEvent(new Event('input',{bubbles:true}));
      year.value=2026;year.dispatchEvent(new Event('change',{bubbles:true}));
    }''')
    page.wait_for_function('!CFB_IMPERIALISM.rendering && CFB_IMPERIALISM.season===2026 && CFB_IMPERIALISM.frameIndex===0')
    page.click('#play');page.wait_for_function('!CFB_IMPERIALISM.rendering && CFB_IMPERIALISM.frameIndex>0',timeout=5000)
    page.click('#play');paused=page.evaluate('CFB_IMPERIALISM.frameIndex');page.wait_for_timeout(1300)
    assert page.evaluate('CFB_IMPERIALISM.frameIndex')==paused
    page.click('#next-week');page.wait_for_function('(previous)=>!CFB_IMPERIALISM.rendering && CFB_IMPERIALISM.frameIndex===previous+1',arg=paused)
    page.click('#previous-week');page.wait_for_function('(previous)=>!CFB_IMPERIALISM.rendering && CFB_IMPERIALISM.frameIndex===previous',arg=paused)
    page.uncheck('#show-logos');page.wait_for_timeout(100)
    assert page.locator('.owner-logo').first.evaluate('(el)=>getComputedStyle(el.parentNode).display')=='none'
    page.check('#show-logos')
    page.click('#zoom-in');page.wait_for_timeout(200)
    assert not check_containment()
    page.click('#reset');page.wait_for_timeout(200)
    assert page.evaluate('document.getElementById("map")._fullLayout.geo.projection.scale')==1
    choose_week(7)
    # Hit-test the map under the logo overlay.
    xy=page.evaluate('''() => {
      const county=CFB_IMPERIALISM_DATA.county_ids.indexOf('20091');
      const f=topojson.feature(CFB_IMPERIALISM_DATA.topology,CFB_IMPERIALISM_DATA.topology.objects.counties).features[county];
      return document.getElementById('map')._fullLayout.geo._subplot.projection(d3.geoCentroid(f));
    }''')
    box=page.locator('#map').bounding_box();page.mouse.move(box['x']+xy[0],box['y']+xy[1]);page.wait_for_timeout(200)
    assert page.locator('#map-tooltip').is_visible()
    assert page.locator('#map-tooltip').evaluate('(el)=>getComputedStyle(el).color')=='rgb(255, 255, 255)'
    page.mouse.click(box['x']+xy[0],box['y']+xy[1]);page.wait_for_timeout(100)
    assert page.locator('#team-select').input_value()!=''
    with page.expect_download(timeout=30000) as download_info:page.click('#export')
    download=download_info.value;download.save_as('/tmp/imperialism-check.svg')
    svg=Path('/tmp/imperialism-check.svg').read_text();assert '2026' in svg and '<image' in svg and 'data:image/png;base64' in svg
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(500)
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    page.screenshot(path='/tmp/imperialism-mobile.png',full_page=True)
    assert not check_containment()
    assert not errors,errors
    assert not [r for r in requests if r.startswith('http')]
    print('Passed: 11 seasons, preseason/postseason, real upset chain, rapid slider/season changes, play/pause, week buttons, logo containment, hover/click, export, mobile, and offline use.')
    browser.close()
