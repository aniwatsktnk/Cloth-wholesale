import uuid
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Product,Customer,Bill,Payment,Movement,ShopSettings
from .services import sell,receive,void_payment,void_bill
class SalesTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user("clerk",password="Strong-Test-Pass-532!")
        ShopSettings.objects.create(name="ร้านทดสอบ",address="ที่อยู่ทดสอบ")
        self.customer=Customer.objects.create(name="ลูกค้าทดสอบ")
        self.p=Product.objects.create(sku="TEST-M",style="TEST",name="เสื้อ",color="ดำ",size="M",retail=150,wholesale=115,stock=20)
        self.q=Product.objects.create(sku="TEST-L",style="TEST",name="เสื้อ",color="ขาว",size="L",retail=150,wholesale=115,stock=20)
    def sale(self,**kwargs):
        args=dict(user=self.user,key=uuid.uuid4(),items=[(self.p.pk,1)],customer=self.customer,discount=0,paid=0,method="cash")
        args.update(kwargs)
        return sell(**args)
    def test_mixed_sizes_and_partial_receipt(self):
        b=self.sale(items=[(self.p.pk,3),(self.q.pk,3)],paid=200)
        self.assertEqual(b.total,690);self.assertEqual(b.balance,490)
        self.assertEqual(b.payments.count(),1)
        self.p.refresh_from_db();self.assertEqual(self.p.stock,17)
    def test_credit_does_not_issue_zero_receipt(self):
        b=self.sale();self.assertEqual(b.payments.count(),0)
    def test_duplicate_sale_is_idempotent(self):
        key=uuid.uuid4()
        self.assertEqual(self.sale(key=key).pk,self.sale(key=key).pk)
        self.p.refresh_from_db();self.assertEqual(self.p.stock,19)
        self.assertEqual(Bill.objects.count(),1)
    def test_duplicate_product_cannot_oversell(self):
        with self.assertRaises(ValidationError):self.sale(items=[(self.p.pk,15),(self.p.pk,15)])
        self.assertEqual(Bill.objects.count(),0)
        self.p.refresh_from_db();self.assertEqual(self.p.stock,20)
    def test_failed_sale_rolls_back_everything(self):
        with self.assertRaises(ValidationError):self.sale(items=[(self.p.pk,1),(self.q.pk,21)])
        self.assertEqual(Movement.objects.count(),0)
        self.assertEqual(Bill.objects.count(),0)
    def test_payment_retry_and_overpayment(self):
        b=self.sale()
        key=uuid.uuid4()
        args=dict(user=self.user,bill_id=b.pk,key=key,value=100,method="transfer",reference="test")
        p=receive(**args);self.assertEqual(receive(**args).pk,p.pk)
        with self.assertRaises(ValidationError):receive(**{**args,"key":uuid.uuid4(),"value":60})
        self.assertEqual(b.balance,50)
    def test_void_restores_stock_only_once(self):
        b=self.sale(paid=150)
        with self.assertRaises(ValidationError):void_bill(user=self.user,bill_id=b.pk,reason="คืน")
        void_payment(user=self.user,payment_id=b.payments.first().pk,reason="คืนเงินสดแล้ว")
        void_bill(user=self.user,bill_id=b.pk,reason="รับสินค้าคืน")
        void_bill(user=self.user,bill_id=b.pk,reason="ซ้ำ")
        self.p.refresh_from_db();self.assertEqual(self.p.stock,20)
    def test_receipt_preserves_seller_and_item(self):
        b=self.sale(paid=150)
        Product.objects.filter(pk=self.p.pk).update(name="เปลี่ยนชื่อ")
        ShopSettings.objects.all().update(name="เปลี่ยนร้าน")
        self.assertEqual(b.seller["name"],"ร้านทดสอบ")
        self.assertIn("เสื้อ",b.lines.first().description)
    def test_auth_and_permissions(self):
        self.assertEqual(self.client.get("/products/").status_code,302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post("/sales/new/").status_code,403)
        self.assertEqual(self.client.post("/stock/").status_code,403)
    def test_templates_render(self):
        self.client.force_login(self.user)
        b=self.sale(paid=150)
        for url in ["/","/products/","/customers/","/sales/",f"/sales/{b.pk}/",f"/receipts/{b.payments.first().pk}/"]:
            self.assertEqual(self.client.get(url).status_code,200,url)

from concurrent.futures import ThreadPoolExecutor
from django.test import TransactionTestCase
from django.db import connection,close_old_connections
from unittest import skipUnless
@skipUnless(connection.vendor=="postgresql","Requires PostgreSQL row locks")
class ConcurrentSalesTests(TransactionTestCase):
    def test_two_clerks_cannot_sell_last_item(self):
        user=get_user_model().objects.create_user("concurrent-clerk")
        ShopSettings.objects.create(name="ร้าน",address="ที่อยู่")
        p=Product.objects.create(sku="LAST",style="LAST",name="ตัวสุดท้าย",color="ดำ",size="M",retail=100,wholesale=90,stock=1)
        def attempt(_):
            close_old_connections()
            try:
                sell(user=user,key=uuid.uuid4(),items=[(p.pk,1)],customer=None,discount=0,paid=100,method="cash")
                return True
            except ValidationError:return False
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,[1,2]))
        self.assertEqual(sum(results),1)
        p.refresh_from_db();self.assertEqual(p.stock,0)
        self.assertEqual(Bill.objects.count(),1)
