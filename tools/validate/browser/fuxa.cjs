// Run from an administrator client with lab access. Does not operate controls.
const fs=require('fs');
const path=require('path');
const {chromium}=require('playwright');

(async()=>{
 const output=path.resolve(process.argv[2]||'.local/acceptance/fuxa');
 fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,args:process.getuid?.()===0?['--no-sandbox']:[]});
 const results=[];
 try {
  for(const [role,address] of [['hmi','10.0.40.10'],['scada','10.0.30.10']]) {
   const base=`http://${address}:1881`;
   const project=await fetch(base+'/api/project').then(r=>{if(!r.ok)throw Error('Project read failed');return r.json()});
   if(project.hmi.views.length!==26)throw Error(role+': expected 26 views');
   const page=await browser.newPage({viewport:{width:1800,height:1100}});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/*',route=>{
    const url=new URL(route.request().url());
    if(['http:','https:'].includes(url.protocol)&&url.hostname!==address)return route.abort();
    return route.continue();
   });
   for(const view of project.hmi.views) {
    const startErrors=errors.length;
    const expectedImages=(view.svgcontent.match(/<image\b/g)||[]).length;
    // FUXA removes editor-only <title>Layer 1</title> nodes. Check the rendered
    // page heading instead so legacy/process views are validated as well.
    const heading=await page.evaluate(svg=>new DOMParser().parseFromString(svg,'image/svg+xml').querySelector('text')?.textContent.trim(),view.svgcontent);
    await page.goto(base+'/home?viewName='+encodeURIComponent(view.name),{waitUntil:'domcontentloaded',timeout:60000});
    if(heading)await page.waitForFunction(t=>document.querySelector('.view-container svg text')?.textContent.trim()===t,heading,{timeout:30000});
    await page.waitForTimeout(1200);
    const rendered=await page.evaluate(async()=>{
     const images=[...document.querySelectorAll('.view-container svg image')];
     const refs=images.map(x=>x.getAttribute('href')||x.getAttributeNS('http://www.w3.org/1999/xlink','href')).filter(Boolean);
     const decoded=await Promise.all(refs.map(src=>new Promise(resolve=>{
      const i=new Image();i.onload=()=>resolve(i.naturalWidth>0&&i.naturalHeight>0);i.onerror=()=>resolve(false);i.src=src;
     })));
     return {images:images.length,decoded:decoded.filter(Boolean).length,failed:decoded.filter(x=>!x).length,
      encodingArtifacts:/\u00c2[\u00b7\u00b0]/.test(document.body.innerText)};
    });
    if(rendered.images!==expectedImages||rendered.failed||rendered.encodingArtifacts||errors.length>startErrors)throw Error(role+'/'+view.id+': visual validation failed '+JSON.stringify({expectedImages,...rendered,errors:errors.slice(startErrors)}));
    const filename=role+'-'+view.id.replace(/[^a-zA-Z0-9_-]/g,'_')+'.png';
    await page.screenshot({path:path.join(output,filename),fullPage:true});
    const result={role,id:view.id,name:view.name,expectedImages,...rendered,screenshot:filename};
    results.push(result);console.log(JSON.stringify(result));
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));
   }
   await page.close();
  }
 } finally {await browser.close()}
 console.log('All 52 FUXA view renders passed with bundled images and external requests blocked.');
})().catch(error=>{console.error(error);process.exit(1)});
