document.querySelectorAll('.add-price').forEach(button=>button.addEventListener('click',()=>{
 const prefix=button.dataset.prefix,total=document.getElementById(`id_${prefix}-TOTAL_FORMS`),n=Number(total.value);
 if(n>=Number(button.dataset.max))return;
 document.getElementById(`${prefix}-rows`).insertAdjacentHTML('beforeend',document.getElementById(`${prefix}-empty`).innerHTML.replaceAll('__prefix__',String(n)));
 total.value=n+1;
}));
