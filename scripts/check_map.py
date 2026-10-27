"""Optional browser smoke check; requires playwright and an installed Chrome/Chromium."""
import argparse
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
URL=(ROOT/'build/closest-teams.html').as_uri()
parser=argparse.ArgumentParser(description='Check the standalone map in Chrome using Playwright.')
parser.add_argument('--browser',default=shutil.which('google-chrome') or shutil.which('chromium'),help='Chrome or Chromium executable')
args=parser.parse_args()
if not args.browser: parser.error('Pass --browser /path/to/chrome')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1050},device_scale_factor=1,accept_downloads=True)
    errors=[];requests=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda request:requests.append(request.url))
    page.goto(URL,wait_until='load')
    page.wait_for_function('window.CFB_MAP?.ready===true',timeout=45000)
    count=page.evaluate('CFB_MAP.logoMetrics.filter(x=>x.visible).length')
    print('Logos rendered:',count)
    assert count==128
    containment=page.evaluate('''() => {
      const projection=document.getElementById('map')._fullLayout.geo._subplot.projection;
      const regions=new Map(CFB_MAP.data.regions.features.map(f=>[f.id,f]));
      const errors=[];
      for(const m of CFB_MAP.logoMetrics.filter(m=>m.visible)) {
        const path=document.createElementNS('http://www.w3.org/2000/svg','path');
        path.setAttribute('d',d3.geoPath(projection)(regions.get(m.team_id)));
        document.getElementById('logo-overlay').appendChild(path);
        for(const x of [-.5,0,.5])for(const y of [-.5,0,.5]) {
          const pt=new DOMPoint(m.center[0]+x*m.size,m.center[1]+y*m.size);
          if(!path.isPointInFill(pt))errors.push({id:m.team_id,x,y});
        }
        path.remove();
      }
      return errors;
    }''')
    print('Logo containment failures:',containment)
    assert not containment
    page.select_option('#team-select','2390')
    assert 'No county' in page.locator('#team-detail').inner_text()
    page.select_option('#team-select','333')
    assert page.locator('#team-name').inner_text()=='Alabama'
    page.check('#show-counties')
    page.wait_for_function('document.getElementById("map").data[0].marker.line.width > 0')
    page.uncheck('#show-logos')
    page.wait_for_timeout(150)
    assert page.locator('.school-logo').first.evaluate('(el)=>getComputedStyle(el.parentNode).display')=='none'
    page.check('#show-logos')
    initial=page.evaluate('CFB_MAP.logoMetrics.find(x=>x.team_id===333).size')
    page.click('#zoom-in')
    page.wait_for_function('document.getElementById("map")._fullLayout.geo.projection.scale > 1')
    page.wait_for_timeout(200)
    assert page.evaluate('CFB_MAP.logoMetrics.find(x=>x.team_id===333).size')>initial
    page.click('#reset');page.wait_for_timeout(200)
    assert page.locator('#team-select').input_value()==''
    assert page.evaluate('document.getElementById("map")._fullLayout.geo.projection.scale')==1
    page.uncheck('#show-counties')
    # County hover and click use the actual map surface, beneath the SVG overlay.
    xy=page.evaluate('''() => {const p=CFB_MAP.data.counties.features.find(f=>f.id==='20091').properties;
      return document.getElementById('map')._fullLayout.geo._subplot.projection([p.longitude,p.latitude]);}''')
    box=page.locator('#map').bounding_box()
    page.mouse.move(box['x']+xy[0],box['y']+xy[1]);page.wait_for_timeout(250)
    assert page.locator('.hovertext').count()>0
    page.mouse.click(box['x']+xy[0],box['y']+xy[1]);page.wait_for_timeout(200)
    assert page.locator('#team-select').input_value()!=''
    page.click('#reset');page.wait_for_timeout(200)
    with page.expect_download(timeout=30000) as info:page.click('#export')
    download=info.value;download.save_as('/tmp/closest-fbs-teams.svg')
    content=Path('/tmp/closest-fbs-teams.svg').read_text()
    assert '<image' in content and 'data:image/png;base64' in content
    page.screenshot(path='/tmp/cfb-map-desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(500)
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    page.screenshot(path='/tmp/cfb-map-mobile.png',full_page=True)
    print('Errors:',errors)
    print('Network requests:',[r for r in requests if r.startswith('http')])
    assert not errors
    assert not [r for r in requests if r.startswith('http')]
    print('Browser checks passed: offline render, 128 fitted logos, containment, selection, hover/click, toggles, zoom/reset, SVG export, mobile layout.')
    browser.close()
