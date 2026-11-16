import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';

// Use an explicitly supplied installed browser library; no downloads or dependency changes.
const require=createRequire(import.meta.url);
const {chromium}=require(process.argv[2]||'playwright');
const output=path.resolve('../../outputs/consolidation/browser');
await mkdir(output,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1500,height:1000}});
const errors=[];
page.on('pageerror',error=>errors.push(error.message));
try {
await page.goto('http://127.0.0.1:5273',{waitUntil:'networkidle'});
await page.getByRole('button',{name:'Company intelligence',exact:true}).click();
await page.getByLabel('Research action',{exact:true}).waitFor();
await page.getByLabel('company',{exact:true}).fill('Swiggy');
await page.screenshot({path:path.join(output,'company-initial.png'),fullPage:true});
await writeFile(path.join(output,'company-initial.txt'),await page.locator('body').innerText());
await writeFile(path.join(output,'initial-errors.json'),JSON.stringify(errors,null,2));
await page.getByLabel('Question or search terms',{exact:true}).fill('consolidated revenue cash flow');
await page.getByRole('button',{name:'Search saved company reports',exact:true}).click();
await page.getByRole('heading',{name:'Company report search · Swiggy',exact:true}).waitFor({timeout:90000});
await page.getByRole('heading',{name:'Company report search · Swiggy',exact:true}).scrollIntoViewIfNeeded();
await page.screenshot({path:path.join(output,'company-results.png')});
const citations=await page.getByRole('link',{name:/Page \d+ ↗/}).evaluateAll(links=>links.map(a=>({text:a.textContent,href:a.getAttribute('href')})));
if(citations.length===0)throw new Error('No report citations appeared');
const sourceResponse=await page.request.get('http://127.0.0.1:5273'+citations[0].href.split('#')[0]);
if(!sourceResponse.ok()||!sourceResponse.headers()['content-type'].includes('application/pdf'))throw new Error('Original source PDF failed');
await page.getByRole('button',{name:'Economy lab',exact:true}).click();
await page.getByLabel('households',{exact:true}).fill('1000');
await page.getByLabel('firms',{exact:true}).fill('10');
await page.getByLabel('steps',{exact:true}).fill('25');
await page.getByRole('button',{name:'Run native CPU economy',exact:true}).click();
await page.getByRole('heading',{name:'SYNTHETIC native economy',exact:true}).waitFor({timeout:180000});
await page.getByRole('heading',{name:'SYNTHETIC native economy',exact:true}).scrollIntoViewIfNeeded();
await page.screenshot({path:path.join(output,'economy-results.png')});
const charts=await page.locator('figure.flagship-chart figcaption').allTextContents();
await writeFile(path.join(output,'acceptance.json'),JSON.stringify({citations,sourcePdfStatus:sourceResponse.status(),charts,errors},null,2));
if(errors.length)throw new Error(errors.join('\n'));
console.log('Report search, original PDF and native economy verified through Q.');
} catch(error) {
  await page.screenshot({path:path.join(output,'failure.png')});
  await writeFile(path.join(output,'failure.txt'),await page.locator('body').innerText());
  throw error;
} finally {
  await browser.close();
}
