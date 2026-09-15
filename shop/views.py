import uuid
from decimal import Decimal
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required,permission_required
from django.core.exceptions import ValidationError
from django.db.models import Sum,F,Q
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from .models import Product,Customer,Bill,Payment,Movement,ShopSettings
from .forms import ProductForm,CustomerForm,SettingsForm,SaleForm,Items,ReceiveForm,StockForm,ReasonForm
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
    return render(request,"customers.html",{"items":Customer.objects.all()})
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
    catalog={str(p.pk):{"style":p.style,"retail":str(p.retail),"wholesale":str(p.wholesale),"stock":p.stock} for p in Product.objects.filter(active=True)}
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
