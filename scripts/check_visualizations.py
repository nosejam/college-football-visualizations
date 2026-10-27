"""Regression checks for tabs, tooltip stacking/contrast, and zoomed map colors."""
import argparse
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--browser',default=shutil.which('google-chrome') or shutil.which('chromium'));args=parser.parse_args()
if not args.browser:parser.error('Pass --browser /path/to/chrome')

def view(page,name):
    return page.query_selector('#view-'+name).content_frame()

def wait_map(frame):
    frame.wait_for_function('window.CFB_IMPERIALISM?.ready && !CFB_IMPERIALISM.rendering',timeout=45000)

def sample_edge_colors(frame,label):
    frame.uncheck('#show-logos');frame.uncheck('#show-borders');frame.wait_for_timeout(150)
    samples=frame.evaluate('''() => {
      const gd=document.getElementById('map'),geo=gd._fullLayout.geo._subplot,w=gd._fullLayout.width,h=gd._fullLayout.height,b=geo.bounds;
      const paths=[...document.querySelectorAll('.choroplethlocation')];
      const candidates=[];for(let y=120;y<h-45;y+=25){candidates.push([10,y],[w-11,y]);}
      for(let x=315;x<w-240;x+=35)candidates.push([x,14],[x,h-14]);
      const result=[];
      for(const [x,y] of candidates){
        if(x>=b[0][0]+2&&x<=b[1][0]-2&&y>=b[0][1]+2&&y<=b[1][1]-2)continue;
        const p=paths.find(path=>[-1,0,1].every(dx=>[-1,0,1].every(dy=>path.isPointInFill(new DOMPoint(x+dx,y+dy)))));
        if(p)result.push({x,y,fill:p.getAttribute('fill')});
        if(result.length===8)break;
      }
      return result;
    }''')
    assert len(samples)>=2,('No land samples outside the original fitted rectangle',label,samples)
    filename=f'/tmp/visualizations-map-{label}.png';frame.locator('#map').screenshot(path=filename)
    pixels=Image.open(filename).convert('RGB')
    for sample in samples:
        expected=tuple(map(int,re.findall(r'\d+',sample['fill'])[:3]))
        actual=pixels.getpixel((round(sample['x']),round(sample['y'])))
        assert max(abs(a-b) for a,b in zip(expected,actual))<=3,(label,sample,expected,actual)
    frame.check('#show-logos');frame.check('#show-borders')
    return len(samples)

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1050},device_scale_factor=1,accept_downloads=True)
    errors=[];requests=[];page.on('pageerror',lambda error:errors.append(str(error)));page.on('request',lambda request:requests.append(request.url))
    page.goto((ROOT/'index.html').as_uri(),wait_until='load')
    assert page.title()=='College Football Visualizations'
    assert page.get_by_role('tab').count()==3
    assert page.locator('#tab-predictor').get_attribute('aria-selected')=='true'
    page.wait_for_function('CFB_VISUALIZATIONS.loaded.length===1')
    predictor=view(page,'predictor');predictor.wait_for_function('CFB_PLAYOFF?.ready&&!CFB_PLAYOFF.state.running')
    page.click('#tab-imperialism')
    imperialism=view(page,'imperialism');wait_map(imperialism)
    imperialism.click('#zoom-in');imperialism.click('#zoom-in');imperialism.wait_for_timeout(300)
    sample_count=sample_edge_colors(imperialism,'zoom')
    clip=imperialism.evaluate('''() => {const gd=document.getElementById('map'),r=gd._fullLayout.geo._subplot.clipRect.node();return [Number(r.getAttribute('x')),Number(r.getAttribute('y')),Number(r.getAttribute('width')),Number(r.getAttribute('height')),gd._fullLayout.width,gd._fullLayout.height];}''')
    assert clip[:2]==[0,0] and clip[2:4]==clip[4:]
    coords=imperialism.evaluate('''() => {const f=topojson.feature(CFB_IMPERIALISM_DATA.topology,CFB_IMPERIALISM_DATA.topology.objects.counties).features.find(f=>f.id==='20091');return document.getElementById('map')._fullLayout.geo._subplot.projection(d3.geoCentroid(f));}''')
    box=imperialism.locator('#map').bounding_box();page.mouse.move(box['x']+coords[0],box['y']+coords[1])
    imperialism.wait_for_function('!document.getElementById("map-tooltip").hidden')
    assert 'Johnson County' in imperialism.locator('#map-tooltip').inner_text()
    assert imperialism.locator('#map-tooltip').evaluate('(el)=>getComputedStyle(el).color')=='rgb(255, 255, 255)'
    assert imperialism.locator('#map-tooltip').evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgb(16, 42, 52)'
    assert imperialism.locator('#map-tooltip').evaluate('''el=>{
      const style=getComputedStyle(el);if(style.position!=='fixed'||Number(style.zIndex)<10000||el.parentNode!==document.body)return false;
      el.style.pointerEvents='auto';const b=el.getBoundingClientRect();const top=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);el.style.pointerEvents='none';return top?.closest('#map-tooltip')===el;
    }''')
    page.screenshot(path='/tmp/visualizations-tooltip.png',full_page=True)
    # Drag/pan must retain the same full-color viewport too.
    page.mouse.move(box['x']+box['width']*.55,box['y']+box['height']*.55)
    page.mouse.down();page.mouse.move(box['x']+box['width']*.55+100,box['y']+box['height']*.55+45,steps=8);page.mouse.up();imperialism.wait_for_timeout(300)
    sample_count+=sample_edge_colors(imperialism,'pan')
    imperialism.select_option('#season-select','2016');imperialism.wait_for_function('CFB_IMPERIALISM.season===2016&&!CFB_IMPERIALISM.rendering')
    index=imperialism.evaluate('CFB_IMPERIALISM_DATA.seasons[2016].frames.findIndex(f=>f.week===7)')
    imperialism.locator('#week-slider').evaluate('(el,index)=>{el.value=index;el.dispatchEvent(new Event("input",{bubbles:true}));}',index)
    imperialism.wait_for_function('(index)=>!CFB_IMPERIALISM.rendering&&CFB_IMPERIALISM.frameIndex===index',arg=index)
    imperialism.select_option('#team-select','2294');imperialism.wait_for_timeout(100)
    before=imperialism.evaluate('({season:CFB_IMPERIALISM.season,index:CFB_IMPERIALISM.frameIndex,scale:document.getElementById("map")._fullLayout.geo.projection.scale})')
    page.click('#tab-circles');circles=view(page,'circles');circles.wait_for_function('window.CFB_CIRCLES?.ready',timeout=30000)
    assert page.locator('#panel-imperialism').get_attribute('aria-hidden')=='true'
    assert page.locator('#panel-imperialism').evaluate('(el)=>el.inert')
    circles.select_option('#team-select','130')
    week6=circles.evaluate('CFB_CIRCLES_DATA.seasons[2026].frames.findIndex(f=>f.week===6)')
    circles.locator('#week-slider').evaluate('(el,index)=>{el.value=index;el.dispatchEvent(new Event("input",{bubbles:true}));}',week6)
    circles.fill('#circle-length','5');circles.click('#find-length');circles.wait_for_function('CFB_CIRCLES.results?.mode==="length"&&!CFB_CIRCLES.state.searching')
    assert circles.evaluate('CFB_CIRCLES.cycle')==[130,201,251,194,2294]
    page.screenshot(path='/tmp/visualizations-circles.png',full_page=True)
    page.locator('#tab-circles').focus();page.keyboard.press('ArrowLeft');imperialism.wait_for_timeout(300)
    assert page.locator('#tab-imperialism').get_attribute('aria-selected')=='true'
    after=imperialism.evaluate('({season:CFB_IMPERIALISM.season,index:CFB_IMPERIALISM.frameIndex,scale:document.getElementById("map")._fullLayout.geo.projection.scale})')
    assert before==after,(before,after)
    assert imperialism.locator('#team-select').input_value()=='2294'
    assert imperialism.locator('#map-tooltip').is_hidden()
    with page.expect_download(timeout=30000) as info:imperialism.click('#export')
    info.value.save_as('/tmp/visualizations-imperialism.svg')
    root=ET.parse('/tmp/visualizations-imperialism.svg').getroot();ns={'s':'http://www.w3.org/2000/svg'}
    geo_clips=[r for clip in root.findall('.//s:clipPath',ns) if clip.get('id','').endswith('geo') for r in clip.findall('s:rect',ns)]
    assert geo_clips
    assert all(r.get('x')=='0' and r.get('y')=='0' for r in geo_clips)
    page.locator('#tab-imperialism').focus();page.keyboard.press('ArrowRight')
    assert page.locator('#tab-circles').get_attribute('aria-selected')=='true'
    assert circles.evaluate('CFB_CIRCLES.cycle')==[130,201,251,194,2294]
    with page.expect_download(timeout=30000) as info:circles.click('#export')
    info.value.save_as('/tmp/visualizations-circles.svg');assert 'data:image/png;base64' in Path('/tmp/visualizations-circles.svg').read_text()
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(500)
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    assert circles.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    page.screenshot(path='/tmp/visualizations-mobile-circles.png',full_page=True)
    page.click('#tab-imperialism');imperialism.wait_for_timeout(350)
    assert imperialism.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    page.screenshot(path='/tmp/visualizations-mobile-map.png',full_page=True)
    assert not errors,errors
    assert not [url for url in requests if url.startswith(('http://','https://'))]
    # The bundle must still work when copied away from the source/assets tree.
    copied=Path('/tmp/cfb-visualizations-isolated');copied.mkdir(exist_ok=True);shutil.copy2(ROOT/'index.html',copied/'index.html')
    isolated=browser.new_page();isolated.goto((copied/'index.html').as_uri()+'#circles',wait_until='load')
    isolated_circles=view(isolated,'circles');isolated_circles.wait_for_function('window.CFB_CIRCLES?.ready',timeout=30000)
    isolated_circles.click('#find-circles');isolated_circles.wait_for_function('CFB_CIRCLES.results&&!CFB_CIRCLES.state.searching')
    assert isolated_circles.evaluate('CFBCycles.valid(CFB_CIRCLES.results.largest,CFBCycles.graph(CFB_CIRCLES.nodes,CFB_CIRCLES.edges))')
    isolated.close();browser.close()
    print(f'Passed: offline single-file tabs, keyboard controls, per-tab state, both exports, tooltip contrast/stacking, {sample_count} colored edge samples after zoom/pan, mobile, and an isolated copied bundle.')
