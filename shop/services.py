from collections import Counter
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Bill,Line,Payment,Product,Movement,ShopSettings

def amount(value):
    try: d=Decimal(str(value))
    except Exception: raise ValidationError("จำนวนเงินไม่ถูกต้อง")
    if not d.is_finite() or d<0 or d>Decimal("9999999999.99") or d != d.quantize(Decimal(".01")):
        raise ValidationError("จำนวนเงินต้องไม่ติดลบ และมีทศนิยมไม่เกิน 2 ตำแหน่ง")
    return d

@transaction.atomic
def sell(*,user,key,items,customer,discount,paid,method,reference=""):
    # Serializing this shop's bills also makes request retries idempotent.
    shop=ShopSettings.objects.select_for_update().first()
    if not shop or not shop.name or not shop.address:
        raise ValidationError("ให้ผู้ดูแลตั้งค่าชื่อและที่อยู่ร้านก่อนขาย")
    old=Bill.objects.filter(request_key=key).first()
    if old: return old
    counts=Counter()
    for pid,qty in items:
        if not isinstance(qty,int) or qty<1 or qty>10000: raise ValidationError("จำนวนสินค้าไม่ถูกต้อง")
        counts[int(pid)]+=qty
    if not counts or len(counts)>100: raise ValidationError("เลือกสินค้า 1 ถึง 100 รายการ")
    products=list(Product.objects.select_for_update().filter(pk__in=counts,active=True).order_by("pk"))
    if len(products)!=len(counts): raise ValidationError("ไม่พบสินค้าหรือสินค้าปิดขาย")
    styles=Counter()
    for p in products:
        if p.stock<counts[p.pk]: raise ValidationError(f"สต๊อก {p.sku} ไม่พอ")
        styles[p.style]+=counts[p.pk]
    rows=[(p,counts[p.pk],p.wholesale if styles[p.style]>=6 else p.retail) for p in products]
    subtotal=sum((q*price for p,q,price in rows),Decimal("0"))
    discount,paid=amount(discount),amount(paid)
    if discount>subtotal: raise ValidationError("ส่วนลดเกินยอดสินค้า")
    total=subtotal-discount
    if paid>total: raise ValidationError("ยอดรับเงินเกินยอดสุทธิ")
    if paid<total and not customer: raise ValidationError("กรุณาเลือกลูกค้าสำหรับยอดค้างชำระ")
    if method not in dict(Payment.METHODS): raise ValidationError("วิธีชำระไม่ถูกต้อง")
    bill=Bill.objects.create(request_key=key,customer=customer,buyer={"name":customer.name,"address":customer.address,"tax_id":customer.tax_id} if customer else {"name":"ลูกค้าหน้าร้าน"},seller=shop.snapshot(),total=total,discount=discount,creator=user)
    for p,q,price in rows:
        Line.objects.create(bill=bill,product=p,description=str(p),quantity=q,price=price,cost=p.cost)
        p.stock-=q;p.save(update_fields=["stock"])
        Movement.objects.create(product=p,delta=-q,reason=bill.number,creator=user)
    if paid: Payment.objects.create(bill=bill,amount=paid,method=method,reference=reference,creator=user,balance_after=total-paid)
    return bill

@transaction.atomic
def receive(*,user,bill_id,key,value,method,reference):
    bill=Bill.objects.select_for_update().get(pk=bill_id)
    old=Payment.objects.filter(request_key=key).first()
    if old:
        if old.bill_id!=bill.pk: raise ValidationError("เลขอ้างอิงซ้ำกับบิลอื่น")
        return old
    value=amount(value)
    if bill.status=="void" or value<=0 or value>bill.balance: raise ValidationError("ยอดรับเงินไม่ถูกต้องหรือบิลยกเลิกแล้ว")
    if method not in dict(Payment.METHODS): raise ValidationError("วิธีชำระไม่ถูกต้อง")
    return Payment.objects.create(bill=bill,request_key=key,amount=value,method=method,reference=reference,creator=user,balance_after=bill.balance-value)

@transaction.atomic
def adjust(*,user,product_id,delta,reason):
    if not reason.strip() or not delta: raise ValidationError("ระบุเหตุผลและจำนวนเปลี่ยนแปลง")
    p=Product.objects.select_for_update().get(pk=product_id)
    if p.stock+delta<0: raise ValidationError("สต๊อกต้องไม่ติดลบ")
    p.stock+=delta;p.save(update_fields=["stock"])
    Movement.objects.create(product=p,delta=delta,reason=reason,creator=user)

@transaction.atomic
def void_payment(*,user,payment_id,reason):
    payment=Payment.objects.get(pk=payment_id)
    Bill.objects.select_for_update().get(pk=payment.bill_id)
    payment.refresh_from_db()
    if not reason.strip(): raise ValidationError("ระบุเหตุผลยกเลิกและวิธีจัดการเงินที่รับไปแล้ว")
    if payment.voided: return
    payment.voided=True
    payment.void_reason=f"{user.username}: {reason}"
    payment.save(update_fields=["voided","void_reason"])

@transaction.atomic
def void_bill(*,user,bill_id,reason):
    bill=Bill.objects.select_for_update().get(pk=bill_id)
    if not reason.strip(): raise ValidationError("กรุณาระบุเหตุผล")
    if bill.status=="void": return
    if bill.paid: raise ValidationError("ต้องยกเลิกใบเสร็จและจัดการคืนเงินจริงก่อนยกเลิกบิล")
    lines=list(bill.lines.all())
    products={p.pk:p for p in Product.objects.select_for_update().filter(pk__in=[l.product_id for l in lines]).order_by("pk")}
    for line in lines:
        p=products[line.product_id];p.stock+=line.quantity;p.save(update_fields=["stock"])
        Movement.objects.create(product=p,delta=line.quantity,reason=f"ยกเลิก {bill.number}: {reason}"[:300],creator=user)
    bill.status="void";bill.void_reason=f"{user.username}: {reason}";bill.save(update_fields=["status","void_reason"])
