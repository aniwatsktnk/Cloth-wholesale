import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
NONNEG = [MinValueValidator(Decimal("0"))]
class Product(models.Model):
    sku=models.CharField("SKU / Barcode",max_length=64,unique=True)
    style=models.CharField("รหัสรุ่น",max_length=64)
    name=models.CharField("ชื่อสินค้า",max_length=160)
    color=models.CharField("สี",max_length=40)
    size=models.CharField("ไซซ์",max_length=30)
    cost=models.DecimalField("ต้นทุน",max_digits=12,decimal_places=2,validators=NONNEG,default=0)
    retail=models.DecimalField("ราคาปลีก",max_digits=12,decimal_places=2,validators=NONNEG)
    wholesale=models.DecimalField("ราคาส่ง (6 ตัวขึ้นไปต่อรุ่น)",max_digits=12,decimal_places=2,validators=NONNEG)
    stock=models.PositiveIntegerField(default=0)
    minimum=models.PositiveIntegerField("จุดเตือนสต๊อก",default=5)
    active=models.BooleanField("เปิดขาย",default=True)
    class Meta:
        ordering=["style","color","size"]
        permissions=[("adjust_stock","Can receive or adjust inventory")]
    def __str__(self): return f"{self.sku} · {self.name} / {self.color} / {self.size}"
class Customer(models.Model):
    name=models.CharField("ชื่อลูกค้า / ร้าน",max_length=160)
    phone=models.CharField("โทรศัพท์",max_length=30,blank=True)
    address=models.TextField("ที่อยู่",blank=True,max_length=1000)
    tax_id=models.CharField("เลขประจำตัวผู้เสียภาษี",max_length=20,blank=True)
    class Meta: ordering=["name"]
    def __str__(self): return self.name
class Bill(models.Model):
    request_key=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    created=models.DateTimeField(auto_now_add=True)
    customer=models.ForeignKey(Customer,on_delete=models.PROTECT,null=True,blank=True)
    buyer=models.JSONField(default=dict)
    seller=models.JSONField(default=dict)
    total=models.DecimalField(max_digits=14,decimal_places=2)
    discount=models.DecimalField(max_digits=14,decimal_places=2,default=0)
    status=models.CharField(max_length=12,default="open")
    void_reason=models.TextField(blank=True)
    creator=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    @property
    def number(self): return f"SO-{self.pk:08d}"
    @property
    def subtotal(self): return self.total+self.discount
    @property
    def paid(self): return sum((p.amount for p in self.payments.all() if not p.voided),Decimal("0"))
    @property
    def balance(self): return self.total-self.paid
class Line(models.Model):
    bill=models.ForeignKey(Bill,on_delete=models.PROTECT,related_name="lines")
    product=models.ForeignKey(Product,on_delete=models.PROTECT)
    description=models.CharField(max_length=300)
    quantity=models.PositiveIntegerField()
    price=models.DecimalField(max_digits=12,decimal_places=2)
    cost=models.DecimalField(max_digits=12,decimal_places=2)
    @property
    def amount(self): return self.price*self.quantity
class Payment(models.Model):
    METHODS=[("cash","เงินสด"),("transfer","โอนเงิน"),("qr","QR"),("card","บัตร")]
    request_key=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    bill=models.ForeignKey(Bill,on_delete=models.PROTECT,related_name="payments")
    amount=models.DecimalField(max_digits=14,decimal_places=2)
    method=models.CharField(max_length=12,choices=METHODS)
    reference=models.CharField(max_length=160,blank=True)
    created=models.DateTimeField(auto_now_add=True)
    creator=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    balance_after=models.DecimalField(max_digits=14,decimal_places=2)
    voided=models.BooleanField(default=False)
    void_reason=models.TextField(blank=True)
    @property
    def number(self): return f"RC-{self.pk:08d}"
class Movement(models.Model):
    product=models.ForeignKey(Product,on_delete=models.PROTECT)
    delta=models.IntegerField()
    reason=models.CharField(max_length=300)
    created=models.DateTimeField(auto_now_add=True)
    creator=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
class ShopSettings(models.Model):
    name=models.CharField("ชื่อร้าน",max_length=160)
    address=models.TextField("ที่อยู่",max_length=1000)
    tax_id=models.CharField("เลขผู้เสียภาษี (ถ้ามี)",max_length=20,blank=True)
    phone=models.CharField("โทรศัพท์",max_length=30,blank=True)
    def snapshot(self): return {k:getattr(self,k) for k in ["name","address","tax_id","phone"]}
