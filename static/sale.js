const catalog=JSON.parse(document.getElementById("catalog").textContent);
const box=document.getElementById("items");
const totalForms=document.getElementById("id_items-TOTAL_FORMS");
function calculate(){
 const rows=[...box.querySelectorAll(".item")].map(row=>({id:row.querySelector("select").value,q:Number(row.querySelector('input[type="number"]').value),deleted:row.querySelector('input[type="checkbox"]').checked}));
 const groups={};
 rows.forEach(r=>{if(!r.deleted && catalog[r.id] && r.q>0) groups[catalog[r.id].style]=(groups[catalog[r.id].style]||0)+r.q});
 let cents=0;
 rows.forEach(r=>{const p=catalog[r.id];if(p&&!r.deleted&&r.q>0)cents+=Math.round(Number(groups[p.style]>=6?p.wholesale:p.retail)*100)*r.q});
 const discount=Math.round(Number(document.getElementById("id_discount").value||0)*100);
 const net=Math.max(0,cents-discount);
 document.getElementById("summary").textContent="ยอดสุทธิประมาณ ฿"+(net/100).toLocaleString("th-TH",{minimumFractionDigits:2})+" (ตรวจสต๊อกอีกครั้งเมื่อบันทึก)";
 return net/100;
}
document.getElementById("add-item").addEventListener("click",()=>{
 const n=Number(totalForms.value);if(n>=100)return;
 box.insertAdjacentHTML("beforeend",document.getElementById("empty-item").innerHTML.replaceAll("__prefix__",String(n)));
 totalForms.value=n+1;
});
document.getElementById("sale-form").addEventListener("input",calculate);
document.getElementById("pay-full").addEventListener("click",()=>{document.getElementById("id_paid").value=calculate().toFixed(2)});
document.getElementById("sale-form").addEventListener("submit",()=>{document.getElementById("submit-sale").disabled=true});
calculate();
