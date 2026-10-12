async (page) => {
  const base = 'http://127.0.0.1:5173';
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  await page.request.post(base+'/api/simulation/actions',{data:{action:'reset'}});
  await page.goto(base+'/commander');
  await page.setViewportSize({width:1536,height:1100});
  await page.getByRole('heading',{name:'ศูนย์ควบคุมภาคพื้น'}).waitFor();
  await page.getByRole('button',{name:'จำลองเหตุการณ์',exact:true}).click();
  await page.getByRole('button',{name:/^พบควัน \/ ไฟ/}).click();
  const began=Date.now();
  await page.getByRole('button',{name:'สร้างเหตุการณ์',exact:true}).click();
  const alert=page.getByRole('alertdialog');
  await alert.waitFor({timeout:2500});
  const alertMs=Date.now()-began;
  await alert.getByRole('button',{name:'อนุมัติและส่งทีม',exact:true}).waitFor({timeout:60000});
  await page.waitForFunction(async()=>{
    const s=await (await fetch('/api/state')).json();
    return ['ready','error','no_plan'].includes(s.incidents.find(i=>i.type==='fire')?.analysis?.status);
  });
  const world=await (await page.request.get(base+'/api/state')).json();
  if(world.missions.length) throw new Error('AI dispatched without commander approval');
  if(!world.gates.find(g=>g.id==='B3').closed) throw new Error('Fire zone not closed');
  const viewports=[];
  const audits=[];
  async function inspect(target,name) {
    for(const width of [320,375,414,768,1536]) {
      await target.setViewportSize({width,height:1000});
      const metrics=await target.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
      if(metrics.scrollWidth>width) throw new Error('Root overflow '+name+' '+width);
      await target.screenshot({path:`output/playwright/${name}-${width}.png`});
      viewports.push({name,...metrics});
    }
    await target.addScriptTag({path:'node_modules/axe-core/axe.min.js'});
    const result=await target.evaluate(async()=>{
      const r=await window.axe.run({exclude:[['i[data-tabster-dummy]']]},{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});
      return r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary})).slice(0,3)}));
    });
    if(result.length) throw new Error('axe '+name+' '+JSON.stringify(result));
    audits.push({name,violations:result});
  }
  await inspect(page,'emergency');
  await page.setViewportSize({width:1536,height:1100});
  await page.keyboard.press('Escape');
  await alert.waitFor({state:'hidden'});
  await page.reload(); await page.getByRole('heading',{name:'ศูนย์ควบคุมภาคพื้น'}).waitFor();
  if(await page.getByRole('alertdialog').count()) throw new Error('Acknowledged alert reopened on refresh');
  await page.request.post(base+'/api/simulation/actions',{data:{action:'reset'}});
  await page.request.post(base+'/api/incidents',{data:{type:'flight_delay'}});
  await page.reload(); await page.getByRole('heading',{name:'ศูนย์ควบคุมภาคพื้น'}).waitFor();
  if(await page.getByRole('alertdialog').count()) throw new Error('Operational incident opened emergency modal');
  await page.getByRole('button',{name:'อนุมัติและส่งทีม',exact:true}).waitFor();
  const crew=await page.context().newPage();
  await crew.goto(base+'/crew');
  await crew.getByRole('heading',{name:'วันนี้คุณอยู่ทีมไหน?'}).waitFor();
  await inspect(crew,'crew-entry');
  await crew.getByRole('textbox',{name:'ค้นหาสมาชิก'}).fill('A17');
  await crew.getByRole('button',{name:/มินตรา/}).click();
  await crew.getByRole('link',{name:'เข้าสู่ mission',exact:true}).click();
  await crew.getByRole('heading',{name:'สวัสดี มินตรา'}).waitFor();
  if(errors.length) throw new Error('Browser exceptions '+errors.join(';'));
  return {passed:true,alertMs,aiSource:world.incidents.find(i=>i.type==='fire').analysis.source,autoDispatch:false,viewports,audits,crewSelection:true,errors};
}
