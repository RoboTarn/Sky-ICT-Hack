async (page) => {
  const base = 'http://127.0.0.1:5173';
  const failures = [];
  page.on('pageerror', e => failures.push(e.message));
  async function state() { const res = await page.request.get(base+'/api/state'); if (!res.ok()) throw new Error('State API failed'); return res.json(); }
  async function waitState(predicate, timeout=2000) {
    const until=Date.now()+timeout;
    while(Date.now()<until) { const value=await state(); if(predicate(value)) return value; await new Promise(r=>setTimeout(r,75)); }
    throw new Error('State did not update within '+timeout+'ms');
  }
  await page.request.post(base+'/api/simulation/actions',{data:{action:'reset'}});
  await page.goto(base+'/commander');
  await page.getByRole('heading',{name:'ศูนย์ควบคุมภาคพื้น'}).waitFor();
  await page.setViewportSize({width:1536,height:1100});
  await page.getByRole('button',{name:'จำลองเหตุการณ์',exact:true}).click();
  await page.getByRole('button',{name:'สร้างเหตุการณ์',exact:true}).click();
  await page.getByRole('button',{name:'อนุมัติและส่งทีม',exact:true}).waitFor({timeout:60000});
  const proposed = await waitState(s=>s.ai.status!=='analyzing',60000);
  await page.getByRole('button',{name:/^แผน 1/}).click();
  const plan = proposed.plans.find(p=>p.rank===1);
  if(plan.after.lateTasks>=plan.before.lateTasks) throw new Error('Recovery does not reduce late tasks');
  const crewPage = await page.context().newPage();
  crewPage.on('pageerror',e=>failures.push(e.message));
  await crewPage.goto(base+'/crew/A17');
  await crewPage.getByRole('heading',{name:'สวัสดี มินตรา'}).waitFor();
  await crewPage.getByText('เชื่อมต่อระบบกลาง',{exact:true}).waitFor();
  await page.locator('.approval-actions').scrollIntoViewIfNeeded();
  const committed=page.waitForResponse(r=>r.url().endsWith('/approve')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'อนุมัติและส่งทีม',exact:true}).click();
  await committed;
  const start = Date.now();
  await crewPage.getByRole('button',{name:'รับ mission',exact:true}).waitFor({timeout:2000});
  const syncMs=Date.now()-start;
  if(syncMs>2000) throw new Error('SSE update exceeded 2 seconds');
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:'output/playwright/commander-recovery.png',fullPage:true});
  const viewports=[];
  const accessibility=[];
  for(const [target,name] of [[page,'commander'],[crewPage,'crew']]) {
    for(const width of [320,375,414,768,1536]) {
      await target.setViewportSize({width,height:width<768?1000:1100});
      await target.evaluate(()=>window.scrollTo(0,0));
      const check=await target.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,unnamed:[...document.querySelectorAll('button')].filter(b=>b.getBoundingClientRect().width>0&&!b.textContent.trim()&&!b.getAttribute('aria-label')).length}));
      if(check.scrollWidth>width||check.unnamed) throw new Error('Viewport/accessibility failure: '+JSON.stringify({name,...check}));
      await target.screenshot({path:`output/playwright/${name}-${width}.png`,fullPage:true});
      viewports.push({name,...check});
    }
    await target.addScriptTag({path:'node_modules/axe-core/axe.min.js'});
    const audit=await target.evaluate(async()=>{
      // Empty Tabster sentinels only redirect keyboard focus; they contain no app content.
      // Preserve Fluent's focus management and audit every actual application element.
      const results=await window.axe.run({exclude:[['i[data-tabster-dummy]']]},{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});
      return results.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary})).slice(0,6)}));
    });
    accessibility.push({name,violations:audit});
    if(audit.length) throw new Error('Accessibility: '+JSON.stringify({name,audit}));
  }
  await crewPage.setViewportSize({width:414,height:1000});
  await crewPage.getByRole('button',{name:'รับ mission',exact:true}).click();
  await waitState(s=>s.missions.some(m=>m.crewId==='A17'&&m.status==='accepted'));
  if(!(await crewPage.getByRole('button',{name:'ออกเดินทาง',exact:true}).isDisabled())) throw new Error('Crew departed before handoff');
  const reliefPage = await page.context().newPage();
  await reliefPage.goto(base+'/crew/A21');
  await reliefPage.getByRole('button',{name:'รับ mission',exact:true}).click();
  await waitState(s=>s.missions.some(m=>m.crewId==='A21'&&m.status==='accepted'));
  await reliefPage.getByRole('button',{name:'ออกเดินทาง',exact:true}).click();
  await waitState(s=>s.missions.some(m=>m.crewId==='A21'&&m.status==='en_route'));
  await reliefPage.getByRole('button',{name:'+1 นาที',exact:true}).click();
  await waitState(s=>s.missions.some(m=>m.crewId==='A21'&&m.status==='completed'));
  await crewPage.getByRole('button',{name:'ออกเดินทาง',exact:true}).click();
  const secondPage=await page.context().newPage();
  await secondPage.goto(base+'/crew/A09');
  await secondPage.getByRole('button',{name:'รับ mission',exact:true}).click();
  await waitState(s=>s.missions.some(m=>m.crewId==='A09'&&m.status==='accepted'));
  await secondPage.getByRole('button',{name:'ออกเดินทาง',exact:true}).click();
  await waitState(s=>s.missions.filter(m=>m.kind==='response').every(m=>m.status==='en_route'));
  await crewPage.getByRole('button',{name:'Route',exact:true}).click();
  await crewPage.screenshot({path:'output/playwright/crew-travelling.png',fullPage:true});
  await crewPage.getByRole('button',{name:'+5 นาที',exact:true}).click();
  await waitState(s=>s.missions.filter(m=>m.kind==='response').every(m=>m.status==='arrived'));
  for(const target of [crewPage,secondPage]) {
    await target.getByRole('button',{name:'เริ่มทำงาน',exact:true}).click();
    await target.getByRole('checkbox').first().waitFor();
    const controls=target.getByRole('checkbox');
    for(let i=0;i<await controls.count();i++) {
      const update=target.waitForResponse(r=>r.url().includes('/actions')&&r.request().method()==='POST');
      await controls.nth(i).click();
      const response=await update; if(!response.ok()) throw new Error('Checklist failed');
    }
  }
  await crewPage.getByRole('button',{name:'+5 นาที',exact:true}).click();
  await waitState(s=>s.now>=660);
  await crewPage.getByRole('button',{name:'+5 นาที',exact:true}).click();
  await waitState(s=>s.now>=960);
  for(const target of [crewPage,secondPage]) {
    await target.getByRole('button',{name:'ยืนยันเสร็จงาน',exact:true}).click();
  }
  const end=await waitState(s=>s.incidents[0].status==='resolved');
  await crewPage.getByText('Mission เสร็จแล้ว',{exact:true}).waitFor();
  await crewPage.screenshot({path:'output/playwright/crew-completed.png',fullPage:true});
  await page.getByRole('button',{name:'คาดการณ์',exact:true}).click();
  await page.getByRole('button',{name:'10 นาที',exact:true}).click();
  await waitState(s=>s.now>=960);
  await page.getByRole('button',{name:'ทีมและอุปกรณ์',exact:true}).click();
  await page.getByRole('textbox',{name:'ค้นหาทีม'}).fill('A17');
  await page.getByRole('heading',{name:'A17 มินตรา'}).waitFor();
  await crewPage.emulateMedia({reducedMotion:'reduce'});
  await crewPage.getByRole('button',{name:'Profile',exact:true}).click();
  await crewPage.getByRole('heading',{name:'Role และขอบเขตงาน'}).waitFor();
  await crewPage.getByRole('combobox',{name:'เปลี่ยนสมาชิกในเดโม'}).focus();
  await crewPage.keyboard.press('Tab');
  await crewPage.waitForFunction(()=>document.activeElement.tagName!=='BODY'&&!document.activeElement.hasAttribute('data-tabster-dummy'));
  const focus=await crewPage.evaluate(()=>({tag:document.activeElement.tagName,outline:getComputedStyle(document.activeElement).outlineStyle}));
  if(focus.outline==='none') throw new Error('Keyboard focus ring is missing');
  if(failures.length) throw new Error(failures.join('\n'));
  await reliefPage.close(); await secondPage.close(); await crewPage.close();
  return {passed:true,syncMs,aiSource:proposed.ai.source,before:plan.before.lateTasks,after:plan.after.lateTasks,incidentStatus:end.incidents[0].status,viewports,accessibility,reducedMotion:true,keyboardFocus:focus,pageErrors:failures};
}
