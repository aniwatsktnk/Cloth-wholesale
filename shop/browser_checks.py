"""Browser checks run explicitly by CI, against disposable test data only."""
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.contrib.auth import get_user_model
from playwright.sync_api import sync_playwright
from .models import Product, Customer, PriceTier, CustomerPrice, ShopSettings, Bill


@override_settings(STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},"staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}})
class WholesaleBrowserChecks(StaticLiveServerTestCase):
    def test_matrix_prices_checkout_and_mobile(self):
        get_user_model().objects.create_superuser('browser-owner',password='Local-Browser-Check-843!')
        ShopSettings.objects.create(name='ร้านทดสอบ',address='ที่อยู่ทดสอบ')
        customer=Customer.objects.create(name='ลูกค้าทดสอบ',credit_days=30)
        products=[]
        for size,color in [('M','ดำ'),('L','ขาว')]:
            p=Product.objects.create(sku=f'TEST-{size}',style='TS001',name='เสื้อทดสอบ',size=size,color=color,retail=150,wholesale=115,stock=50)
            PriceTier.objects.create(product=p,minimum_quantity=12,price=100)
            products.append(p)
        CustomerPrice.objects.create(product=products[0],customer=customer,price=80)
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            page=browser.new_page(viewport={'width':1280,'height':900})
            errors=[]
            page.on('pageerror',lambda error: errors.append(str(error)))
            page.goto(self.live_server_url+'/login/')
            page.locator('#id_username').fill('browser-owner')
            page.locator('#id_password').fill('Local-Browser-Check-843!')
            page.locator('button[type=submit], button').first.click()
            page.wait_for_url(self.live_server_url+'/')
            page.goto(self.live_server_url+'/sales/new/')
            page.locator('#matrix-style').select_option('TS001')
            for p in products:
                page.locator(f'.matrix-qty[data-product="{p.pk}"]').fill('6')
            page.locator('#matrix-add').click()
            self.assertIn('1,200.00',page.locator('#summary').inner_text())
            page.locator('#id_customer').select_option(str(customer.pk))
            self.assertIn('1,080.00',page.locator('#summary').inner_text())
            page.locator('#id_paid').fill('200')
            page.locator('#submit-sale').click()
            page.wait_for_url('**/sales/*/')
            self.assertIn('880.00',page.locator('main').inner_text())
            page.locator('#id_value').fill('100')
            page.locator('button').filter(has_text='รับเงินและออกใบเสร็จ').click()
            page.wait_for_url('**/receipts/*/')
            page.goto(self.live_server_url+'/receipts/')
            page.locator('input[name="payments"]').nth(0).check()
            page.locator('input[name="payments"]').nth(1).check()
            page.get_by_role('button',name='สร้างใบสรุปรวมใบเสร็จ').click()
            page.wait_for_url('**/receipt-bundles/*/')
            self.assertIn('300.00',page.locator('article').inner_text())
            self.assertEqual(page.locator('article h3').count(),1)
            page.emulate_media(media='print')
            self.assertTrue(page.locator('article h1').is_visible())
            page.emulate_media(media='screen')
            page.goto(self.live_server_url+'/reports/money/')
            self.assertIn('300.00',page.locator('main').inner_text())
            page.goto(self.live_server_url+'/receivables/')
            self.assertIn('780.00',page.locator('main').inner_text())
            page.goto(self.live_server_url+f'/products/{products[0].pk}/prices/')
            page.locator('.add-price[data-prefix="tiers"]').click()
            self.assertEqual(page.locator('#id_tiers-TOTAL_FORMS').input_value(),'3')
            page.set_viewport_size({'width':390,'height':844})
            page.goto(self.live_server_url+'/sales/new/')
            page.locator('#matrix-style').select_option('TS001')
            self.assertTrue(page.locator('#matrix-add').is_visible())
            self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'))
            self.assertEqual(errors,[])
            browser.close()
