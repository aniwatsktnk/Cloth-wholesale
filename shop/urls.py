from django.urls import path
from . import views as v
urlpatterns=[
 path("receipts/",v.receipt_list,name="receipt_list"),
 path("receipt-bundles/<int:pk>/",v.receipt_bundle,name="receipt_bundle"),
 path("receipt-bundles/<int:pk>/cancel/",v.cancel_bundle,name="cancel_bundle"),
 path("reports/money/",v.money_report,name="money_report"),
 path("products/<int:pk>/edit/",v.product_edit,name="product_edit"),
 path("products/<int:pk>/prices/",v.product_prices,name="product_prices"),
 path("customers/<int:pk>/edit/",v.customer_edit,name="customer_edit"),
 path("receivables/",v.receivables,name="receivables"),
 path("sales/<int:pk>/due-date/",v.due_date_edit,name="due_date_edit"),
 path("",v.dashboard,name="home"),
 path("products/",v.products,name="products"),path("products/add/",v.product_add,name="product_add"),
 path("customers/",v.customers,name="customers"),path("customers/add/",v.customer_add,name="customer_add"),
 path("settings/",v.settings_edit,name="settings"),path("stock/",v.stock,name="stock"),
 path("sales/new/",v.sale_new,name="sale_new"),path("sales/",v.bills,name="bills"),
 path("sales/<int:pk>/",v.bill_detail,name="bill"),path("sales/<int:pk>/payment/",v.payment_add,name="payment_add"),
 path("sales/<int:pk>/cancel/",v.cancel_bill,name="cancel_bill"),
 path("receipts/<int:pk>/",v.receipt,name="receipt"),path("receipts/<int:pk>/cancel/",v.cancel_payment,name="cancel_payment")
]
