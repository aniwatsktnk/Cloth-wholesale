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

from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import Permission
from .models import PriceTier,CustomerPrice,AuditEvent
from .forms import ProductForm,Tiers

class ExpansionTests(TestCase):
    setUp=SalesTests.setUp
    sale=SalesTests.sale

    def manager(self):
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='shop',codename__in=['change_product','change_customer','change_bill','add_bill']))
        self.client.force_login(self.user)

    def test_tiers_use_mixed_variant_total_and_legacy_fallback(self):
        PriceTier.objects.create(product=self.p,minimum_quantity=12,price=95)
        PriceTier.objects.create(product=self.q,minimum_quantity=12,price=105)
        bill=self.sale(items=[(self.p.pk,6),(self.q.pk,6)])
        self.assertEqual(bill.total,1200)
        bill=self.sale(items=[(self.p.pk,3),(self.q.pk,3)])
        self.assertEqual(bill.total,690)

    def test_customer_price_overrides_tiers_and_is_not_applied_to_other_customer(self):
        CustomerPrice.objects.create(product=self.p,customer=self.customer,price=80)
        PriceTier.objects.create(product=self.p,minimum_quantity=6,price=90)
        self.assertEqual(self.sale(items=[(self.p.pk,6)]).total,480)
        another=Customer.objects.create(name='อื่น')
        self.assertEqual(self.sale(items=[(self.p.pk,6)],customer=another).total,540)

    def test_zero_special_price_is_valid(self):
        CustomerPrice.objects.create(product=self.p,customer=self.customer,price=0)
        bill=self.sale();self.assertEqual(bill.total,0);self.assertEqual(bill.payments.count(),0)

    def test_credit_term_and_explicit_due_date(self):
        self.customer.credit_days=30;self.customer.save()
        self.assertEqual(self.sale().due_date,timezone.localdate()+timedelta(days=30))
        due=timezone.localdate()+timedelta(days=7)
        self.assertEqual(self.sale(due_date=due).due_date,due)
        with self.assertRaises(ValidationError): self.sale(due_date=timezone.localdate()-timedelta(days=1))

    def test_tier_changes_do_not_reprice_existing_bill(self):
        bill=self.sale();PriceTier.objects.create(product=self.p,minimum_quantity=1,price=50)
        self.customer.credit_days=60;self.customer.save()
        bill.refresh_from_db();self.assertEqual(bill.total,150);self.assertEqual(bill.lines.get().price,150)
        self.assertEqual(bill.due_date,timezone.localdate())

    def test_edits_preserve_stock_and_snapshot_and_are_audited(self):
        self.manager();bill=self.sale()
        self.p.refresh_from_db()
        data={k:getattr(self.p,k) for k in ProductForm.Meta.fields};data.update(name='ชื่อใหม่',stock=999,cost=999)
        self.assertEqual(self.client.post(f'/products/{self.p.pk}/edit/',data).status_code,302)
        self.p.refresh_from_db();self.assertEqual(self.p.stock,19);self.assertEqual(self.p.cost,0)
        self.assertIn('เสื้อ',bill.lines.get().description)
        event=AuditEvent.objects.get(object_type='product');self.assertEqual(event.changes['name']['after'],'ชื่อใหม่')
        self.assertEqual(self.client.post(f'/customers/{self.customer.pk}/edit/',{'name':'ลูกค้าใหม่','phone':'','address':'','tax_id':'','credit_days':15}).status_code,302)
        bill.refresh_from_db();self.assertEqual(bill.buyer['name'],'ลูกค้าทดสอบ')

    def test_new_pages_and_permissions(self):
        self.client.force_login(self.user)
        for path in [f'/products/{self.p.pk}/edit/',f'/products/{self.p.pk}/prices/',f'/customers/{self.customer.pk}/edit/']:
            self.assertEqual(self.client.post(path,{}).status_code,403)
        self.manager()
        for path in [f'/products/{self.p.pk}/edit/',f'/products/{self.p.pk}/prices/',f'/customers/{self.customer.pk}/edit/','/receivables/','/sales/new/']:
            self.assertEqual(self.client.get(path).status_code,200,path)

    def test_receivables_aging_excludes_void_and_paid_and_counts_partial_receipt(self):
        self.client.force_login(self.user)
        bill=self.sale(paid=50)
        Bill.objects.filter(pk=bill.pk).update(due_date=timezone.localdate()-timedelta(days=31))
        unknown=self.sale();Bill.objects.filter(pk=unknown.pk).update(due_date=None)
        self.sale(paid=150)
        void=self.sale();void_bill(user=self.user,bill_id=void.pk,reason='test')
        response=self.client.get('/receivables/?bucket=31_60')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['totals']['all'],250)
        self.assertEqual(response.context['totals']['31_60'],100)
        self.assertEqual(response.context['totals']['unknown'],150)
        self.assertEqual(len(response.context['page']),1)
        receive(user=self.user,bill_id=bill.pk,key=uuid.uuid4(),value=100,method='cash',reference='')
        self.assertEqual(self.client.get('/receivables/').context['totals']['all'],150)

    def test_due_date_change_requires_reason_and_preserves_money(self):
        self.manager();bill=self.sale();url=f'/sales/{bill.pk}/due-date/'
        self.client.post(url,{'due_date':'2027-01-01','reason':''})
        bill.refresh_from_db();self.assertEqual(bill.due_date,timezone.localdate())
        self.assertEqual(self.client.post(url,{'due_date':'2027-01-01','reason':'ตกลงกับลูกค้าแล้ว'}).status_code,302)
        bill.refresh_from_db();self.assertEqual(str(bill.due_date),'2027-01-01');self.assertEqual(bill.balance,150)
        self.assertTrue(AuditEvent.objects.filter(object_type='bill',object_id=bill.pk).exists())

    def test_pricing_form_saves_and_rejects_duplicate_threshold(self):
        self.manager()
        payload={'tiers-TOTAL_FORMS':'1','tiers-INITIAL_FORMS':'0','tiers-0-minimum_quantity':'12','tiers-0-price':'100',
                 'specials-TOTAL_FORMS':'1','specials-INITIAL_FORMS':'0','specials-0-customer':str(self.customer.pk),'specials-0-price':'80'}
        response=self.client.post(f'/products/{self.p.pk}/prices/',payload)
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.p.price_tiers.get().price,100);self.assertEqual(self.p.customer_prices.get().price,80)
        payload.update({'tiers-TOTAL_FORMS':'2','tiers-1-minimum_quantity':'12','tiers-1-price':'90'})
        self.assertFalse(Tiers(payload,instance=self.p,prefix='tiers').is_valid())

    def test_catalog_does_not_include_cost_and_handles_html_as_data(self):
        self.manager();self.p.name='<script>alert(1)</script>';self.p.save()
        response=self.client.get('/sales/new/')
        self.assertNotIn('cost',response.context['catalog'][str(self.p.pk)])
        self.assertNotContains(response,'<script>alert(1)</script>')

    def test_form_rejects_non_https_image(self):
        data={k:getattr(self.p,k) for k in ProductForm.Meta.fields};data['image_url']='http://example.com/image.jpg'
        self.assertFalse(ProductForm(data,instance=self.p).is_valid())

from .models import ReceiptBundle
from .services import combine_receipts
class ReceiptBundleTests(TestCase):
    setUp=SalesTests.setUp
    sale=SalesTests.sale
    def payments(self):
        bill=self.sale(items=[(self.p.pk,2)],paid=100)
        second=receive(user=self.user,bill_id=bill.pk,key=uuid.uuid4(),value=50,method='transfer',reference='test')
        return bill,[bill.payments.first().pk,second.pk]
    def test_combination_is_snapshot_without_new_money_or_stock(self):
        bill,ids=self.payments();stock=Product.objects.get(pk=self.p.pk).stock
        bundle=combine_receipts(user=self.user,key=uuid.uuid4(),payment_ids=ids)
        self.assertEqual(bundle.total,150);self.assertEqual(Payment.objects.count(),2)
        self.assertEqual(len(bundle.snapshot['bills']),1)
        self.assertEqual(bundle.snapshot['bills'][0]['lines'][0]['quantity'],2)
        self.assertEqual(bill.balance,150);self.assertEqual(Product.objects.get(pk=self.p.pk).stock,stock)
        self.assertFalse(bundle.invalid)
    def test_retry_and_duplicate_selection(self):
        bill,ids=self.payments();key=uuid.uuid4()
        one=combine_receipts(user=self.user,key=key,payment_ids=ids+[ids[0]])
        self.assertEqual(combine_receipts(user=self.user,key=key,payment_ids=ids).pk,one.pk)
        self.assertEqual(one.payments.count(),2);self.assertEqual(ReceiptBundle.objects.count(),1)
    def test_mixed_customers_and_walk_in_rejected(self):
        bill,ids=self.payments()
        other=self.sale(customer=Customer.objects.create(name='อื่น'),paid=150)
        with self.assertRaises(ValidationError): combine_receipts(user=self.user,key=uuid.uuid4(),payment_ids=[ids[0],other.payments.first().pk])
        a=self.sale(customer=None,paid=150);b=self.sale(customer=None,paid=150)
        with self.assertRaises(ValidationError): combine_receipts(user=self.user,key=uuid.uuid4(),payment_ids=[a.payments.first().pk,b.payments.first().pk])
    def test_multiple_bills_and_changed_identity(self):
        bill,ids=self.payments();other=self.sale(paid=150)
        bundle=combine_receipts(user=self.user,key=uuid.uuid4(),payment_ids=[ids[0],other.payments.first().pk])
        self.assertEqual(bundle.total,250);self.assertEqual(len(bundle.snapshot['bills']),2)
        Bill.objects.filter(pk=other.pk).update(buyer={'name':'เปลี่ยนชื่อ'})
        with self.assertRaises(ValidationError): combine_receipts(user=self.user,key=uuid.uuid4(),payment_ids=[ids[0],other.payments.first().pk])
        self.assertEqual(bundle.snapshot['buyer']['name'],'ลูกค้าทดสอบ')
    def test_void_source_invalidates_summary_and_remains_visible_in_print(self):
        bill,ids=self.payments();bundle=combine_receipts(user=self.user,key=uuid.uuid4(),payment_ids=ids)
        void_payment(user=self.user,payment_id=ids[0],reason='รับคืนแล้ว')
        self.assertTrue(bundle.invalid)
        with self.assertRaises(ValidationError): combine_receipts(user=self.user,key=uuid.uuid4(),payment_ids=ids)
        self.client.force_login(self.user)
        response=self.client.get(f'/receipt-bundles/{bundle.pk}/?paper=80')
        self.assertContains(response,'document-invalid');self.assertEqual(bundle.total,150)
    def test_invalid_selection(self):
        bill,ids=self.payments()
        for values in [[ids[0]],[ids[0],ids[0]],ids+[99999],list(range(101))]:
            with self.assertRaises(ValidationError): combine_receipts(user=self.user,key=uuid.uuid4(),payment_ids=values)
    def test_permissions_cancel_and_money_report(self):
        bill,ids=self.payments();self.client.force_login(self.user)
        self.assertEqual(self.client.post('/receipts/',{'key':str(uuid.uuid4()),'payments':ids}).status_code,403)
        self.user.user_permissions.add(*Permission.objects.filter(codename__in=['add_receiptbundle','change_receiptbundle'],content_type__app_label='shop'))
        response=self.client.post('/receipts/',{'key':str(uuid.uuid4()),'payments':ids})
        self.assertEqual(response.status_code,302);bundle=ReceiptBundle.objects.get()
        report=self.client.get('/reports/money/');self.assertEqual(report.context['total'],150)
        self.assertEqual(self.client.post(f'/receipt-bundles/{bundle.pk}/cancel/',{'reason':'พิมพ์ผิด'}).status_code,302)
        bundle.refresh_from_db();self.assertTrue(bundle.cancelled)
        self.assertEqual(self.client.get('/reports/money/').context['total'],150)
        void_payment(user=self.user,payment_id=ids[0],reason='คืนเงิน')
        self.assertEqual(self.client.get('/reports/money/').context['total'],50)
    def test_filters_and_invalid_dates(self):
        bill,ids=self.payments();self.client.force_login(self.user)
        response=self.client.get('/receipts/',{'q':f'SO-{bill.pk:08d}','customer':self.customer.pk})
        self.assertEqual(response.context['page'].paginator.count,2)
        self.assertContains(self.client.get('/receipts/?start=invalid'),'errorlist')
        response=self.client.get('/reports/money/?start=2026-09-30&end=2026-09-01')
        self.assertEqual(response.context['total'],0);self.assertContains(response,'errorlist')
