import uuid
from decimal import Decimal
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required,permission_required
from django.core.exceptions import ValidationError
from django.db.models import Sum,F,Q
from django.db import transaction
from django.core.paginator import Paginator
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from .models import Product,Customer,Bill,Payment,Movement,ShopSettings,AuditEvent
from .forms import ProductForm,CustomerForm,SettingsForm,SaleForm,Items,ReceiveForm,StockForm,ReasonForm,Tiers,SpecialPrices,DueDateForm
from .services import sell,receive,adjust,void_bill,void_payment

def errors(form,exc): form.add_error(None,"; ".join(exc.messages))
@login_required
def dashboard(request):
    bills=Bill.objects.filter(status="open").prefetch_related("payments")
    today=timezone.localdate()
    day=bills.filter(created__date=today).aggregate(v=Sum("total"))["v"] or 0
    debt=sum((b.balance for b in bills),Decimal("0"))
    days=[today-timedelta(days=i) for i in reversed(range(7))]
    trend=[{"date":d,"total":bills.filter(created__date=d).aggregate(v=Sum("total"))["v"] or 0} for d in days]
    return render(request,"dashboard.html",{"day":day,"debt":debt,"trend":trend,"low":Product.objects.filter(active=True,stock__lte=F("minimum"))[:30],"recent":bills.order_by("-pk")[:10]})
@login_required
def products(request):
    q=request.GET.get("q","")
    items=Product.objects.filter(Q(sku__icontains=q)|Q(name__icontains=q)|Q(style__icontains=q))
    return render(request,"products.html",{"items":items,"q":q})
@permission_required("shop.add_product",raise_exception=True)
def product_add(request):
    form=ProductForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        form.save();messages.success(request,"เพิ่มสินค้าแล้ว กรุณารับสต๊อกที่เมนูสต๊อก");return redirect("products")
    return render(request,"form.html",{"form":form,"title":"เพิ่มสินค้าแยกสีและไซซ์"})
@login_required
def customers(request):
    q=request.GET.get("q","")
    return render(request,"customers.html",{"items":Customer.objects.filter(Q(name__icontains=q)|Q(phone__icontains=q)),"q":q})
@permission_required("shop.add_customer",raise_exception=True)
def customer_add(request):
    form=CustomerForm(request.POST or None)
    if request.method=="POST" and form.is_valid(): form.save();return redirect("customers")
    return render(request,"form.html",{"form":form,"title":"เพิ่มลูกค้า"})
@permission_required("shop.change_shopsettings",raise_exception=True)
def settings_edit(request):
    form=SettingsForm(request.POST or None,instance=ShopSettings.objects.first())
    if request.method=="POST" and form.is_valid(): form.save();messages.success(request,"บันทึกข้อมูลร้านแล้ว");return redirect("home")
    return render(request,"form.html",{"form":form,"title":"ข้อมูลร้านสำหรับใบเสร็จ"})
@permission_required("shop.add_bill",raise_exception=True)
def sale_new(request):
    form=SaleForm(request.POST or None,initial={"key":uuid.uuid4()})
    items=Items(request.POST or None,prefix="items")
    if request.method=="POST" and form.is_valid() and items.is_valid():
        lines=[(d["product"].pk,d["quantity"]) for d in items.cleaned_data if d and not d.get("DELETE")]
        try:
            b=sell(user=request.user,items=lines,**form.cleaned_data)
            return redirect("bill",pk=b.pk)
        except ValidationError as e: errors(form,e)
    catalog={str(p.pk):{"sku":p.sku,"name":p.name,"color":p.color,"size":p.size,"style":p.style,"retail":str(p.retail),"wholesale":str(p.wholesale),"stock":p.stock,
        "tiers":{str(t.minimum_quantity):str(t.price) for t in p.price_tiers.all()},
        "special":{str(c.customer_id):str(c.price) for c in p.customer_prices.all()}}
        for p in Product.objects.filter(active=True).prefetch_related("price_tiers","customer_prices")}
    return render(request,"sale.html",{"form":form,"items":items,"catalog":catalog})
@login_required
def bills(request):
    qs=Bill.objects.select_related("customer").prefetch_related("payments").order_by("-pk")
    if request.GET.get("q"): qs=qs.filter(Q(buyer__name__icontains=request.GET["q"]))
    return render(request,"bills.html",{"items":qs[:200]})
@login_required
def bill_detail(request,pk):
    b=get_object_or_404(Bill.objects.prefetch_related("lines","payments"),pk=pk)
    form=ReceiveForm(initial={"key":uuid.uuid4(),"value":b.balance})
    return render(request,"bill.html",{"bill":b,"form":form})
@permission_required("shop.add_payment",raise_exception=True)
def payment_add(request,pk):
    if request.method!="POST": return redirect("bill",pk=pk)
    form=ReceiveForm(request.POST)
    if form.is_valid():
        try:
            p=receive(user=request.user,bill_id=pk,**form.cleaned_data)
            return redirect("receipt",pk=p.pk)
        except ValidationError as e: errors(form,e)
    return render(request,"form.html",{"form":form,"title":"รับชำระเงินเพิ่ม"})
@login_required
def receipt(request,pk):
    p=get_object_or_404(Payment.objects.select_related("bill","creator"),pk=pk)
    return render(request,"receipt.html",{"payment":p,"bill":p.bill,"thermal":request.GET.get("paper")=="80"})
@permission_required("shop.adjust_stock",raise_exception=True)
def stock(request):
    form=StockForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        try:
            d=form.cleaned_data;adjust(user=request.user,product_id=d["product"].pk,delta=d["delta"],reason=d["reason"])
            return redirect("stock")
        except ValidationError as e: errors(form,e)
    return render(request,"stock.html",{"form":form,"movements":Movement.objects.select_related("product","creator").order_by("-pk")[:100]})
@permission_required("shop.change_bill",raise_exception=True)
def cancel_bill(request,pk):
    form=ReasonForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        try:
            void_bill(user=request.user,bill_id=pk,reason=form.cleaned_data["reason"])
            return redirect("bill",pk=pk)
        except ValidationError as e: errors(form,e)
    return render(request,"form.html",{"form":form,"title":"ยกเลิกบิลและคืนสินค้าเข้าสต๊อก"})
@permission_required("shop.change_payment",raise_exception=True)
def cancel_payment(request,pk):
    form=ReasonForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        try:
            void_payment(user=request.user,payment_id=pk,reason=form.cleaned_data["reason"])
            return redirect("receipt",pk=pk)
        except ValidationError as e: errors(form,e)
    return render(request,"form.html",{"form":form,"title":"ยกเลิกใบเสร็จ (ไม่ลบประวัติ)"})

def audit(user,obj,before,after):
    changes={k:{"before":before.get(k),"after":v} for k,v in after.items() if before.get(k)!=v}
    if changes: AuditEvent.objects.create(actor=user,object_type=obj._meta.model_name,object_id=obj.pk,changes=changes)

def snapshot(obj,fields): return {k:str(getattr(obj,k)) for k in fields}

@permission_required("shop.change_product",raise_exception=True)
@transaction.atomic
def product_edit(request,pk):
    product=get_object_or_404(Product.objects.select_for_update(),pk=pk)
    before=snapshot(product,ProductForm.Meta.fields)
    form=ProductForm(request.POST or None,instance=product)
    if request.method=="POST" and form.is_valid():
        form.save();audit(request.user,product,before,snapshot(product,ProductForm.Meta.fields))
        messages.success(request,"บันทึกสินค้าแล้ว");return redirect("products")
    return render(request,"form.html",{"form":form,"title":f"แก้ไขสินค้า {product.sku}"})

@permission_required("shop.change_customer",raise_exception=True)
@transaction.atomic
def customer_edit(request,pk):
    customer=get_object_or_404(Customer.objects.select_for_update(),pk=pk)
    before=snapshot(customer,CustomerForm.Meta.fields)
    form=CustomerForm(request.POST or None,instance=customer)
    if request.method=="POST" and form.is_valid():
        form.save();audit(request.user,customer,before,snapshot(customer,CustomerForm.Meta.fields))
        messages.success(request,"บันทึกลูกค้าแล้ว บิลเดิมยังคงข้อมูลเดิม");return redirect("customers")
    return render(request,"form.html",{"form":form,"title":f"แก้ไขลูกค้า {customer.name}"})

@permission_required("shop.change_product",raise_exception=True)
@transaction.atomic
def product_prices(request,pk):
    product=get_object_or_404(Product.objects.select_for_update(),pk=pk)
    def prices():
        return {"tiers":list(product.price_tiers.values_list("minimum_quantity","price")),"special":list(product.customer_prices.values_list("customer_id","price"))}
    before={k:str(v) for k,v in prices().items()}
    tiers=Tiers(request.POST or None,instance=product,prefix="tiers")
    specials=SpecialPrices(request.POST or None,instance=product,prefix="specials")
    if request.method=="POST":
        valid_tiers=tiers.is_valid();valid_specials=specials.is_valid()
        if valid_tiers and valid_specials:
            tiers.save();specials.save()
            audit(request.user,product,before,{k:str(v) for k,v in prices().items()})
            messages.success(request,"บันทึกราคาแล้ว ใช้กับบิลใหม่เท่านั้น");return redirect("product_prices",pk=pk)
    return render(request,"prices.html",{"product":product,"tiers":tiers,"specials":specials})

@login_required
def receivables(request):
    today=timezone.localdate();customer_id=request.GET.get("customer","");bucket=request.GET.get("bucket","")
    qs=Bill.objects.filter(status="open").select_related("customer").prefetch_related("payments").order_by("due_date","pk")
    if customer_id.isdigit(): qs=qs.filter(customer_id=int(customer_id))
    totals={k:Decimal("0") for k in ["all","not_due","1_30","31_60","over_60","unknown"]}
    rows=[];groups={}
    for b in qs:
        balance=b.balance
        if balance<=0: continue
        days=(today-b.due_date).days if b.due_date else None
        category="unknown" if days is None else "not_due" if days<=0 else "1_30" if days<=30 else "31_60" if days<=60 else "over_60"
        totals[category]+=balance;totals["all"]+=balance
        group=groups.setdefault(b.customer_id,{"customer":b.customer,"balance":Decimal("0"),"overdue":Decimal("0")})
        group["balance"]+=balance
        if days is not None and days>0: group["overdue"]+=balance
        if not bucket or category==bucket: rows.append({"bill":b,"balance":balance,"days":days,"overdue":days is not None and days>0})
    page=Paginator(rows,50).get_page(request.GET.get("page"))
    return render(request,"receivables.html",{"page":page,"totals":totals,"groups":groups.values(),"customers":Customer.objects.all(),"customer_id":customer_id,"bucket":bucket,"today":today})

@permission_required("shop.change_bill",raise_exception=True)
@transaction.atomic
def due_date_edit(request,pk):
    bill=get_object_or_404(Bill.objects.select_for_update(),pk=pk)
    form=DueDateForm(request.POST or None,initial={"due_date":bill.due_date})
    if request.method=="POST" and form.is_valid():
        if bill.status=="void": form.add_error(None,"แก้วันครบกำหนดบิลที่ยกเลิกแล้วไม่ได้")
        else:
            old=str(bill.due_date);bill.due_date=form.cleaned_data["due_date"];bill.save(update_fields=["due_date"])
            audit(request.user,bill,{"due_date":old},{"due_date":str(bill.due_date),"reason":form.cleaned_data["reason"]})
            messages.success(request,"บันทึกวันครบกำหนดแล้ว");return redirect("bill",pk=pk)
    return render(request,"form.html",{"form":form,"title":f"วันครบกำหนด {bill.number}"})

@login_required
def receipt_list(request):
    from .forms import ReceiptFilterForm,BundleForm
    from .models import ReceiptBundle
    from .services import combine_receipts
    filters=ReceiptFilterForm(request.GET)
    qs=Payment.objects.select_related('bill','creator').order_by('-pk')
    if filters.is_valid():
        data=filters.cleaned_data
        if data.get('customer'): qs=qs.filter(bill__customer=data['customer'])
        if data.get('start'): qs=qs.filter(created__date__gte=data['start'])
        if data.get('end'): qs=qs.filter(created__date__lte=data['end'])
        if data.get('q'):
            q=data['q'].strip();number=q.split('-')[-1]
            if number.isdigit() and len(number)>18:
                qs=qs.none()
            elif number.isdigit():
                qs=qs.filter(bill_id=int(number)) if q.upper().startswith('SO-') else qs.filter(pk=int(number))
            else: qs=qs.filter(bill__buyer__name__icontains=q)
    else: qs=qs.none()
    form=BundleForm(request.POST or None,initial={'key':uuid.uuid4()})
    if request.method=='POST':
        if not request.user.has_perm('shop.add_receiptbundle'):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        if form.is_valid():
            try:
                bundle=combine_receipts(user=request.user,key=form.cleaned_data['key'],payment_ids=list(form.cleaned_data['payments'].values_list('pk',flat=True)))
                return redirect('receipt_bundle',pk=bundle.pk)
            except ValidationError as e: errors(form,e)
    page=Paginator(qs,100).get_page(request.GET.get('page'))
    params=request.GET.copy();params.pop('page',None)
    return render(request,'receipt_list.html',{'page':page,'filters':filters,'form':form,'query':params.urlencode(),
        'selected':request.POST.getlist('payments'),'bundles':ReceiptBundle.objects.select_related('customer').order_by('-pk')[:30]})

@login_required
def receipt_bundle(request,pk):
    from .models import ReceiptBundle
    bundle=get_object_or_404(ReceiptBundle.objects.select_related('creator'),pk=pk)
    return render(request,'receipt_bundle.html',{'bundle':bundle,'data':bundle.snapshot,'invalid':bundle.invalid,'thermal':request.GET.get('paper')=='80'})

@permission_required('shop.change_receiptbundle',raise_exception=True)
@transaction.atomic
def cancel_bundle(request,pk):
    from .models import ReceiptBundle
    bundle=get_object_or_404(ReceiptBundle.objects.select_for_update(),pk=pk)
    form=ReasonForm(request.POST or None)
    form.fields['reason'].label='เหตุผลยกเลิกใบสรุป (ไม่กระทบใบเสร็จต้นฉบับ)'
    if request.method=='POST' and form.is_valid():
        if not bundle.cancelled:
            bundle.cancelled=True;bundle.cancel_reason=f'{request.user.username}: {form.cleaned_data["reason"]}'[:500]
            bundle.save(update_fields=['cancelled','cancel_reason'])
            audit(request.user,bundle,{'cancelled':False},{'cancelled':True,'reason':bundle.cancel_reason})
        return redirect('receipt_bundle',pk=pk)
    return render(request,'form.html',{'form':form,'title':f'ยกเลิกใบสรุป {bundle.number}'})

@login_required
def money_report(request):
    from .forms import MoneyReportForm
    from django.db.models.functions import TruncDate
    from django.db.models import Count
    today=timezone.localdate()
    form=MoneyReportForm(request.GET or {'start':today.isoformat(),'end':today.isoformat()})
    payments=Payment.objects.none()
    if form.is_valid(): payments=Payment.objects.filter(created__date__range=(form.cleaned_data['start'],form.cleaned_data['end']))
    valid=payments.filter(voided=False)
    method_totals={r['method']:r for r in valid.values('method').annotate(total=Sum('amount'),count=Count('pk'))}
    methods=[{'name':label,'total':method_totals.get(key,{}).get('total',0),'count':method_totals.get(key,{}).get('count',0)} for key,label in Payment.METHODS]
    days=valid.annotate(day=TruncDate('created')).values('day').annotate(total=Sum('amount'),count=Count('pk')).order_by('-day')
    return render(request,'money_report.html',{'form':form,'methods':methods,'days':days,
        'total':valid.aggregate(value=Sum('amount'))['value'] or 0,'count':valid.count(),'void_count':payments.filter(voided=True).count()})
