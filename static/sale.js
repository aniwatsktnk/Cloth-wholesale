const catalog=JSON.parse(document.getElementById('catalog').textContent);
const box=document.getElementById('items');
const totalForms=document.getElementById('id_items-TOTAL_FORMS');
const customer=document.getElementById('id_customer');
const money=cents=>(cents/100).toLocaleString('th-TH',{minimumFractionDigits:2});
function price(p,count){
 if(Object.hasOwn(p.special,customer.value))return Math.round(Number(p.special[customer.value])*100);
 const levels={1:p.retail,6:p.wholesale,...p.tiers};
 const level=Math.max(...Object.keys(levels).map(Number).filter(n=>n<=count));
 return Math.round(Number(levels[level])*100);
}
function rows(){return [...box.querySelectorAll('.item')].map(row=>({row,id:row.querySelector('select').value,q:Number(row.querySelector('input[type="number"]').value),deleted:row.querySelector('input[type="checkbox"]').checked}));}
function calculate(){
 const list=rows(),groups=Object.create(null);let cents=0;
 list.forEach(r=>{if(!r.deleted&&catalog[r.id]&&Number.isInteger(r.q)&&r.q>0)groups[catalog[r.id].style]=(groups[catalog[r.id].style]||0)+r.q;});
 list.forEach(r=>{
  let label=r.row.querySelector('.item-price');if(!label){label=document.createElement('p');label.className='item-price';r.row.append(label);}
  const p=catalog[r.id];
  if(p&&!r.deleted&&Number.isInteger(r.q)&&r.q>0){const unit=price(p,groups[p.style]);cents+=unit*r.q;label.textContent=`฿${money(unit)} / ตัว · รวม ฿${money(unit*r.q)}${Object.hasOwn(p.special,customer.value)?' · ราคาเฉพาะลูกค้า':''}`;}else label.textContent='';
 });
 const discount=Math.round(Number(document.getElementById('id_discount').value||0)*100);
 const net=Math.max(0,cents-discount);
 document.getElementById('summary').textContent='ยอดสุทธิประมาณ ฿'+money(net)+' (ตรวจราคาและสต๊อกอีกครั้งเมื่อบันทึก)';return net/100;
}
function addRow(){
 const n=Number(totalForms.value);if(n>=100)return null;
 box.insertAdjacentHTML('beforeend',document.getElementById('empty-item').innerHTML.replaceAll('__prefix__',String(n)));
 totalForms.value=n+1;return box.lastElementChild;
}
document.getElementById('add-item').addEventListener('click',addRow);
document.getElementById('sale-form').addEventListener('input',calculate);
document.getElementById('sale-form').addEventListener('change',calculate);
document.getElementById('pay-full').addEventListener('click',()=>{document.getElementById('id_paid').value=calculate().toFixed(2);});
document.getElementById('sale-form').addEventListener('submit',()=>{document.getElementById('submit-sale').disabled=true;});
const styles=document.getElementById('matrix-style'),matrix=document.getElementById('matrix'),status=document.getElementById('matrix-status');
[...new Set(Object.values(catalog).map(p=>p.style))].sort((a,b)=>a.localeCompare(b,'th')).forEach(style=>{
 const option=document.createElement('option');option.value=style;option.textContent=style+' · '+Object.values(catalog).find(p=>p.style===style).name;styles.append(option);
});
styles.addEventListener('change',()=>{
 matrix.replaceChildren();status.textContent='';
 const products=Object.entries(catalog).filter(([id,p])=>p.style===styles.value);if(!products.length)return;
 const colors=[...new Set(products.map(([id,p])=>p.color))],sizes=[...new Set(products.map(([id,p])=>p.size))];
 const ordered=['XS','S','M','L','XL','XXL','2XL','3XL','4XL'];sizes.sort((a,b)=>{const ai=ordered.indexOf(a.toUpperCase()),bi=ordered.indexOf(b.toUpperCase());return ai>=0&&bi>=0?ai-bi:a.localeCompare(b,'th',{numeric:true});});
 const table=document.createElement('table'),head=table.createTHead().insertRow();
 ['สี / ไซซ์',...sizes].forEach(s=>{const th=document.createElement('th');th.textContent=s;head.append(th);});
 const body=table.createTBody();colors.forEach(color=>{
  const row=body.insertRow();const th=document.createElement('th');th.textContent=color;row.append(th);
  sizes.forEach(size=>{const cell=row.insertCell(),matches=products.filter(([id,p])=>p.color===color&&p.size===size);
   if(!matches.length){cell.textContent='—';return;}
   matches.forEach(([id,p])=>{const label=document.createElement('label');const desc=document.createElement('small');desc.textContent=p.sku+' · เหลือ '+p.stock;
    const input=document.createElement('input');input.type='number';input.min=0;input.max=Math.min(10000,p.stock);input.step=1;input.placeholder='0';input.className='matrix-qty';input.dataset.product=id;input.disabled=p.stock<=0;input.setAttribute('aria-label',`${p.sku} ${color} ${size} จำนวน`);
    label.append(desc,input);cell.append(label);
   });
  });
 });matrix.append(table);
});
document.getElementById('matrix-add').addEventListener('click',()=>{
 const selected=[...matrix.querySelectorAll('input')].filter(i=>Number(i.value)>0);
 if(!selected.length){status.textContent='กรอกจำนวนในตารางก่อน';return;}
 if(selected.some(i=>!i.checkValidity())){status.textContent='จำนวนต้องเป็นจำนวนเต็มและไม่เกินสต๊อก';return;}
 const existing=rows(),changes=[];let newCount=0;
 for(const input of selected){const id=input.dataset.product,q=Number(input.value),current=existing.filter(r=>r.id===id&&!r.deleted);const count=current.reduce((n,r)=>n+(Number.isInteger(r.q)?r.q:0),0);
  if(count+q>catalog[id].stock||count+q>10000){status.textContent='จำนวนรวม '+catalog[id].sku+' เกินสต๊อกหรือ 10,000 ตัว';return;}
  if(!current.length)newCount++;changes.push({input,id,q,current});
 }
 const empty=existing.filter(r=>!r.id&&!r.deleted);
 if(Number(totalForms.value)+Math.max(0,newCount-empty.length)>100){status.textContent='บิลรองรับสูงสุด 100 รายการ';return;}
 changes.forEach(({input,id,q,current})=>{const row=current.length?current[0].row:empty.length?empty.shift().row:addRow();row.querySelector('select').value=id;const qty=row.querySelector('input[type="number"]');qty.value=current.length?Number(qty.value||0)+q:q;input.value='';});
 calculate();status.textContent='เพิ่มสินค้าเข้ารายการในบิลแล้ว ตรวจยอดก่อนบันทึก';
});
calculate();
