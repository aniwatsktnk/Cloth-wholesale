import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations,models
import django.core.validators
import django.db.models.deletion
class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="Product",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("sku",models.CharField("SKU / Barcode",max_length=64,unique=True)),
            ("style",models.CharField("รหัสรุ่น",max_length=64)),
            ("name",models.CharField("ชื่อสินค้า",max_length=160)),
            ("color",models.CharField("สี",max_length=40)),
            ("size",models.CharField("ไซซ์",max_length=30)),
            ("cost",models.DecimalField("ต้นทุน",decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0"))], default=0)),
            ("retail",models.DecimalField("ราคาปลีก",decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
            ("wholesale",models.DecimalField("ราคาส่ง (6 ตัวขึ้นไปต่อรุ่น)",decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
            ("stock",models.PositiveIntegerField(default=0)),
            ("minimum",models.PositiveIntegerField("จุดเตือนสต๊อก",default=5)),
            ("active",models.BooleanField("เปิดขาย",default=True)),
        ],options={"ordering":["style","color","size"],"permissions":[("adjust_stock","Can receive or adjust inventory")]}),
        migrations.CreateModel(name="Customer",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("name",models.CharField("ชื่อลูกค้า / ร้าน",max_length=160)),
            ("phone",models.CharField("โทรศัพท์",max_length=30,blank=True)),
            ("address",models.TextField("ที่อยู่",blank=True,max_length=1000)),
            ("tax_id",models.CharField("เลขประจำตัวผู้เสียภาษี",max_length=20,blank=True)),
        ],options={"ordering":["name"]}),
        migrations.CreateModel(name="ShopSettings",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("name",models.CharField("ชื่อร้าน",max_length=160)),
            ("address",models.TextField("ที่อยู่",max_length=1000)),
            ("tax_id",models.CharField("เลขผู้เสียภาษี (ถ้ามี)",max_length=20,blank=True)),
            ("phone",models.CharField("โทรศัพท์",max_length=30,blank=True)),
        ],options={}),
        migrations.CreateModel(name="Bill",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("request_key",models.UUIDField(default=uuid.uuid4,unique=True,editable=False)),
            ("created",models.DateTimeField(auto_now_add=True)),
            ("customer",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="shop.customer", null=True, blank=True)),
            ("buyer",models.JSONField(default=dict)),
            ("seller",models.JSONField(default=dict)),
            ("total",models.DecimalField(decimal_places=2, max_digits=14)),
            ("discount",models.DecimalField(decimal_places=2, max_digits=14, default=0)),
            ("status",models.CharField(max_length=12,default="open")),
            ("void_reason",models.TextField(blank=True)),
            ("creator",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ],options={}),
        migrations.CreateModel(name="Line",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("bill",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="shop.bill", related_name="lines")),
            ("product",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="shop.product")),
            ("description",models.CharField(max_length=300)),
            ("quantity",models.PositiveIntegerField()),
            ("price",models.DecimalField(decimal_places=2, max_digits=12)),
            ("cost",models.DecimalField(decimal_places=2, max_digits=12)),
        ],options={}),
        migrations.CreateModel(name="Payment",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("request_key",models.UUIDField(default=uuid.uuid4,unique=True,editable=False)),
            ("bill",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="shop.bill", related_name="payments")),
            ("amount",models.DecimalField(decimal_places=2, max_digits=14)),
            ("method",models.CharField(max_length=12,choices=[("cash","เงินสด"),("transfer","โอนเงิน"),("qr","QR"),("card","บัตร")])),
            ("reference",models.CharField(max_length=160, blank=True)),
            ("created",models.DateTimeField(auto_now_add=True)),
            ("creator",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ("balance_after",models.DecimalField(decimal_places=2, max_digits=14)),
            ("voided",models.BooleanField(default=False)),
            ("void_reason",models.TextField(blank=True)),
        ],options={}),
        migrations.CreateModel(name="Movement",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("product",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="shop.product")),
            ("delta",models.IntegerField()),
            ("reason",models.CharField(max_length=300)),
            ("created",models.DateTimeField(auto_now_add=True)),
            ("creator",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ],options={}),
    ]
