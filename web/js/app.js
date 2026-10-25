const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>(Number(v||0)/100).toFixed(2);
const today=()=>new Date().toLocaleDateString('sv-SE');
const statusText={pending:'待确认',confirmed:'已确认',completed:'已完成',exception:'异常待处理',cancelled:'已取消'};
const kindText={subsidy:'高龄补贴',recharge:'充值',consumption:'服务消费',refund:'服务退款',reversal:'入账冲正',opening:'期初额度',migration:'迁移标记',legacy_recharge:'历史充值',legacy_order:'历史消费',legacy_refund:'历史退款',legacy_adjust:'历史调整'};
const roleText={community:'社区',admin:'养老公司',worker:'服务员',customer:'顾客'};
let ME,CONF,currentTab='orders',loadId=0,modalUrls=[];
const navs={customer:[['orders','我的订单'],['book','选人预约'],['ledger','服务币明细']],worker:[['orders','服务订单'],['route','行程安排'],['batches','酬金依据']],admin:[['orders','订单看板'],['manage','人员与项目'],['ledger','服务账本'],['settle','酬金结算'],['contracts','社区合同']],community:[['orders','服务看板'],['contracts','公司入驻'],['people','老人档案'],['ledger','补贴与账本'],['settle','公司结算']]};
let orderFilters={};
function toast(msg){$('toast').textContent=msg;$('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,3500);}
function closeModal(){modalUrls.forEach(URL.revokeObjectURL);modalUrls=[];$('modal-root').innerHTML='';}
function modal(title,html){closeModal();$('modal-root').innerHTML=`<div class="modal-backdrop"><section class="modal"><div class="row spread"><h3>${esc(title)}</h3><button class="btn btn-small btn-plain" id="modal-close">关闭</button></div>${html}</section></div>`;$('modal-close').onclick=closeModal;}
function field(label,name,type='text',value='',extra=''){return `<label class="fl" for="f-${name}">${label}</label><input id="f-${name}" name="${name}" type="${type}" value="${esc(value)}" ${extra}>`;}
function options(rows,value='id',label='name'){return rows.map(r=>`<option value="${r[value]}">${esc(r[label])}</option>`).join('');}
function empty(message='暂无记录'){return `<div class="card muted center">${esc(message)}</div>`;}
function table(headers,rows){return `<div class="tblwrap"><table class="tbl"><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>'<tr>'+r.map(c=>`<td>${c??''}</td>`).join('')+'</tr>').join('')}</tbody></table></div>`;}
function bindForm(id,fn){$(id).onsubmit=async e=>{e.preventDefault();const btn=e.submitter;try{if(btn)btn.disabled=true;await fn(Object.fromEntries(new FormData(e.target)),e.target);}catch(err){toast(err.message);}finally{if(btn?.isConnected)btn.disabled=false;}};}
async function action(path,body={}){await API.call(path,{method:'POST',body});toast('已记录');closeModal();await render();}
function reasonModal(title,path){modal(title,`<form id="reason-form">${field('原因（必填）','reason','text','','required maxlength="500"')}<p>操作会留下记录，不能覆盖原始账务或凭证。</p><button class="btn" type="submit">确认记录</button></form>`);bindForm('reason-form',d=>action(path,d));}
function showLogin(){$('boot-splash').hidden=true;$('app-view').hidden=true;$('login-view').hidden=false;closeModal();}
function showApp(){$('login-view').hidden=true;$('app-view').hidden=false;$('boot-splash').hidden=true;$('top-hello').textContent=`${ME.name} · ${roleText[ME.role]}`;currentTab='orders';orderFilters={};render();}
async function render(){
 const id=++loadId;
 $('tabbar').innerHTML=navs[ME.role].map(([k,v])=>`<button data-tab="${k}" class="${k===currentTab?'active':''}">${v}</button>`).join('');
 document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{currentTab=b.dataset.tab;render();});
 Maps.instances.forEach((_,key)=>Maps.destroy(key));$('main').innerHTML='<div class="card muted">正在读取…</div>';
 try{
  const fn={orders:renderOrders,book:renderBooking,ledger:renderLedger,route:renderRoute,batches:renderBatches,manage:renderManage,people:renderPeople,contracts:renderContracts,settle:renderSettlement}[currentTab];
  const html=await fn();if(id!==loadId)return;
  if(typeof html==='string')$('main').innerHTML=html;
 }catch(e){if(id===loadId)$('main').innerHTML=empty(e.message);}
}
async function renderOrders(){
 const [res,s]=await Promise.all([API.call('/orders?'+new URLSearchParams(orderFilters)),API.call('/summary')]);
 $('main').innerHTML=`<div class="pagehead"><div><p class="eyebrow">SERVICE RECORDS</p><h1>${ME.role==='customer'?'我的养老服务':'服务记录与结算看板'}</h1></div><span class="chip blue">服务币结算</span></div><div class="stats"><div class="stat"><div class="num">${s.orders_count}</div><div class="lbl">筛选前订单总数</div></div><div class="stat"><div class="num">${s.completed_count||0}</div><div class="lbl">完成订单</div></div><div class="stat"><div class="num">${s.exception_count||0}</div><div class="lbl">异常待处理</div></div><div class="stat"><div class="num">${money(ME.role==='customer'?s.available_cents:s.service_cents)}</div><div class="lbl">${ME.role==='customer'?'可预约额度':'有凭证净服务币'}</div></div></div><div class="notice">每笔服务：自主选人 → 确认上门 → 地址定位打卡 → 结束合影 → 记账与结算依据。旧记录如缺少凭证，会单独标明。</div><form id="filter-form" class="card row"><select name="status" aria-label="订单状态" style="width:auto"><option value="">全部状态</option>${Object.entries(statusText).map(([k,v])=>`<option value="${k}" ${orderFilters.status===k?'selected':''}>${v}</option>`).join('')}</select><input aria-label="开始日期" name="from" type="date" style="width:auto" value="${esc(orderFilters.from||'')}"><input aria-label="结束日期" name="to" type="date" style="width:auto" value="${esc(orderFilters.to||'')}"><button class="btn" type="submit">筛选</button><button type="button" id="clear-filter" class="btn btn-plain">清空</button></form><div id="order-list">${res.orders.map(orderCard).join('')||empty()}</div>`;
 bindForm('filter-form',d=>{orderFilters=Object.fromEntries(Object.entries(d).filter(([,v])=>v));return render();});$('clear-filter').onclick=()=>{orderFilters={};render();};wireOrders();
}
function orderCard(o){
 let buttons=`<button class="btn btn-small btn-plain" data-order="${o.id}" data-act="details">记录与凭证</button>`;
 if(ME.role==='worker'){
  if(o.status==='pending')buttons+=`<button class="btn btn-small" data-order="${o.id}" data-act="confirm">确认上门</button>`;
  if(o.status==='confirmed')buttons+=`<button class="btn btn-small btn-green" data-order="${o.id}" data-act="${o.checkin_at?'complete':'checkin'}">${o.checkin_at?'结束服务并合影':'开始服务打卡'}</button>`;
  if(['pending','confirmed'].includes(o.status))buttons+=`<button class="btn btn-small btn-plain" data-order="${o.id}" data-act="exception">上报异常</button>`;
 }
 if(['admin','worker'].includes(ME.role)&&['pending','confirmed','exception'].includes(o.status)&&!o.checkin_at)buttons+=`<button class="btn btn-small btn-plain" data-order="${o.id}" data-act="reschedule">改期</button>`;
 if(['admin','community','customer'].includes(ME.role)&&o.status!=='cancelled'&&(!o.paid||ME.role==='community'&&!o.legacy&&o.proof_id))buttons+=`<button class="btn btn-small btn-plain" data-order="${o.id}" data-act="cancel">${o.paid?'核实退款':'取消预约'}</button>`;
 return `<article class="card order-card ${esc(o.status)}"><div class="head"><span class="time">${esc(o.sched_start)} · ${o.duration_minutes}分钟</span><span class="chip ${o.status==='completed'?'green':'blue'}">${statusText[o.status]}</span></div><div class="who">${esc(o.item_name)} · ${money(o.price_cents)} 服务币</div><p class="meta">#${o.id}　${esc(o.company_name)} / ${esc(o.worker_name)} → ${esc(o.customer_name)}<br>${esc(o.customer_address)}<br>${o.legacy?'历史记录 · 原有凭证不完整，未纳入新结算':o.proof_id?'已留存地址打卡与结束合影':o.checkin_at?'已打卡，服务进行中':'等待服务开始'}${o.exception_note?'<br>异常：'+esc(o.exception_note):''}</p><div class="row">${buttons}</div></article>`;
}
function wireOrders(){document.querySelectorAll('[data-order]').forEach(b=>b.onclick=async()=>{const id=b.dataset.order,a=b.dataset.act;try{
 if(a==='details')await showOrder(id);
 else if(a==='confirm')await action(`/orders/${id}/confirm`);
 else if(a==='cancel'||a==='exception')reasonModal(a==='cancel'?'取消／退款依据':'上报服务异常',`/orders/${id}/${a}`);
 else if(a==='reschedule'){modal('调整预约时间',`<form id="reschedule-form">${field('新预约时间','sched_start','datetime-local','','required')}<p>需重新由服务员确认。</p><button class="btn" type="submit">保存改期</button></form>`);bindForm('reschedule-form',d=>action(`/orders/${id}/reschedule`,d));}
 else if(a==='checkin')checkinModal(id);
 else if(a==='complete')completeModal(id);
 }catch(e){toast(e.message);}});}
async function showOrder(id){const d=await API.call('/orders/'+id),o=d.order;
 modal('订单 #'+id+' · 履约记录',`<p>${esc(o.company_name)} / ${esc(o.worker_name)} → ${esc(o.customer_name)}</p><p>${esc(o.item_name)} · ${money(o.price_cents)} 服务币</p><div class="notice">${o.legacy?'历史记录，缺少完整凭证。':'服务器记录打卡和完成时间；定位及合影由服务员提交，真实性需社区／公司核验。'}</div><p>开始时间：${esc(o.checkin_at||'未打卡')}<br>实际地址：${esc(o.checkin_address||'—')}<br>WGS84：${esc(o.checkin_lat??'—')}, ${esc(o.checkin_lng??'—')}<br>定位精度：${esc(o.checkin_accuracy??'—')} 米<br>结束记录：${esc(o.completed_at||'—')}</p>${d.proof?`<img id="proof-photo" alt="服务结束合影" class="proof-photo"><p class="small hash">凭证 #${d.proof.id} · SHA256 ${esc(d.proof.sha256)}</p>`:''}<h4>操作流水</h4>${d.logs.map(l=>`<div class="audit"><strong>${esc(l.action)}</strong><span class="muted small"> ${esc(l.created_at)}</span><br>${esc(l.actor)}<br><span class="small">${esc(l.detail)}</span></div>`).join('')||'暂无操作记录'}`);
 if(d.proof){const blob=await(await API.raw(`/orders/${id}/photo`)).blob();if($('proof-photo')){const url=URL.createObjectURL(blob);modalUrls.push(url);$('proof-photo').src=url;}}
}
async function renderLedger(){
 const d=await API.call('/ledger');let creditHtml='';
 if(ME.role==='community'){
  const p=await API.call('/people');creditHtml=`<section class="card"><h3>发放补贴／充值入账</h3><form id="credit-form"><div class="frow"><div><label class="fl">业务类型</label><select name="kind"><option value="subsidy">高龄补贴</option><option value="recharge">服务币充值</option></select></div><div>${field('每人服务币额度','amount','number','','required min="0.01" step="0.01"')}</div></div>${field('业务批次号（用于防止重复发放）','reference','text','','required maxlength="100"')}${field('发放依据／充值凭据编号','note','text','','required')}<div class="people-picks">${p.people.filter(x=>x.active).map(u=>`<label><input type="checkbox" name="customer_ids" value="${u.id}"> ${esc(u.name)} <small>${u.subsidy_eligible?'已核定补贴资格':'无补贴资格'} · 余额${money(u.balance_cents)}</small></label>`).join('')}</div><button class="btn" type="submit">确认入账并留存流水</button></form></section>`;
 }
 let balances={};if(ME.role==='customer'){let b=0;[...d.ledger].reverse().forEach(l=>{b+=l.delta_cents;balances[l.id]=b;});}
 $('main').innerHTML=`<div class="pagehead"><h1>${ME.role==='community'?'补贴、充值与可查账本':'服务币流水'}</h1></div><div class="notice">服务币是内部结算记账单位。每笔充值、补贴、消费、退款均有编号；原流水只可追加冲正，不可覆盖。平台订阅费另向养老公司收取。</div>${creditHtml}<section class="card"><h3>全部流水</h3>${table(['流水 / 时间','老人 / 类型','变动服务币',...(ME.role==='customer'?['变动后余额']:[]),'订单 / 业务单号','依据 / 操作人'],d.ledger.map(l=>[`${l.id}<br>${esc(l.created_at)}`,`${esc(l.customer_name)}<br>${esc(kindText[l.kind]||l.kind)}`,`<span class="${l.delta_cents>=0?'money-plus':'money-minus'}">${l.delta_cents>0?'+':''}${money(l.delta_cents)}</span>`,...(ME.role==='customer'?[money(balances[l.id])]:[]),`${l.order_id?'#'+l.order_id:'—'}<br>${esc(l.reference)}`,`${esc(l.note)}<br><span class="small muted">${esc(l.actor_name||'历史承接')}</span>${ME.role==='community'&&['subsidy','recharge'].includes(l.kind)&&!l.reversed?`<br><button class="btn btn-small btn-plain" data-reverse="${l.id}">冲正</button>`:l.reversed?'<br>已追加冲正':''}`]))}</section>`;
 if($('credit-form'))bindForm('credit-form',(d,form)=>action('/credits',{...d,amount_cents:Math.round(Number(d.amount)*100),customer_ids:new FormData(form).getAll('customer_ids').map(Number)}));
 document.querySelectorAll('[data-reverse]').forEach(b=>b.onclick=()=>reasonModal('冲正入账流水 #'+b.dataset.reverse,`/ledger/${b.dataset.reverse}/reverse`));
}
async function renderBatches(){const d=await API.call('/batches');$('main').innerHTML=`<h1>结算依据批次</h1><p class="notice">记录的是对账／酬金核算依据，实际货币兑付比例和付款由合同及线下确认。本系统不发起资金划转。</p>${batchCards(d.batches)}`;wireBatches();}
function batchCards(rows){return rows.map(b=>`<article class="card"><h3>#${b.id} · ${b.kind==='company'?'社区与公司结算':'公司与员工酬金'} <span class="chip green">${money(b.total_cents)} ${b.kind==='company'?'服务币':'核算单位'}</span></h3><p>${esc(b.company_name)} ${esc(b.worker_name||'')}<br>${esc(b.from_date)} 至 ${esc(b.to_date)}<br>依据单号：${esc(b.reference)}</p><div class="row"><button class="btn btn-small btn-plain" data-batch="${b.id}">查看明细</button><button class="btn btn-small" data-export="${b.id}">导出 CSV</button></div></article>`).join('')||empty();}
function wireBatches(){document.querySelectorAll('[data-export]').forEach(b=>b.onclick=()=>API.download(`/batches/${b.dataset.export}/export.csv`,`结算依据-${b.dataset.export}.csv`).catch(e=>toast(e.message)));document.querySelectorAll('[data-batch]').forEach(b=>b.onclick=async()=>{try{const d=await API.call('/batches/'+b.dataset.batch);modal('结算依据 #'+d.batch.id,entryTable(d.entries,d.batch.kind));wireOrders();}catch(e){toast(e.message);}});}
function entryTable(rows,kind){return table(['订单 / 类型','老人 / 服务员','服务币','酬金单位','凭证'],rows.map(e=>[`#${e.order_id}<br>${e.event==='refund'?'退款冲正':'完成服务'}`,`${esc(e.customer_name)} / ${esc(e.worker_name)}`,money(e.amount_cents),money(e.pay_cents),`<button class="btn btn-small btn-plain" data-order="${e.order_id}" data-act="details">查看凭证 #${e.proof_id}</button>`]));}
document.addEventListener('DOMContentLoaded',async()=>{
 // Clear the prior version's static cache once; private data is never cached.
 if('serviceWorker'in navigator)navigator.serviceWorker.getRegistrations().then(rs=>rs.forEach(r=>r.unregister()));
 if('caches'in window)caches.keys().then(ks=>ks.filter(k=>/care|elder/i.test(k)).forEach(k=>caches.delete(k)));
 $('login-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{const d=await API.call('/login',{method:'POST',body:{phone:$('login-phone').value,password:$('login-pwd').value}});API.setToken(d.token);ME=d;$('login-err').hidden=true;showApp();}catch(err){$('login-err').textContent=err.message;$('login-err').hidden=false;}finally{b.disabled=false;}};
 $('btn-logout').onclick=async()=>{try{await API.call('/logout',{method:'POST'});}finally{API.setToken('');showLogin();}};
 $('btn-pwd').onclick=()=>{modal('修改本地账号密码',`<form id="pwd-form">${field('原密码','old_password','password','','required')}${field('新密码（至少6位）','new_password','password','','required minlength="6"')}<p><button class="btn" type="submit">保存密码</button></p></form>`);bindForm('pwd-form',async d=>{await API.call('/auth/change-password',{method:'POST',body:d});toast('密码已修改');closeModal();});};
 try{CONF=await API.call('/meta');Maps.init(CONF.map);if(API.token){ME=await API.call('/me');showApp();}else showLogin();}catch(e){showLogin();toast(e.message);}
});
