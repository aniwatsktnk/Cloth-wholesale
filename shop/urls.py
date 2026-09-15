from django.urls import path
from . import views as v
urlpatterns=[
 path("",v.dashboard,name="home"),
 path("products/",v.products,name="products"),path("products/add/",v.product_add,name="product_add"),
 path("customers/",v.customers,name="customers"),path("customers/add/",v.customer_add,name="customer_add"),
 path("settings/",v.settings_edit,name="settings"),path("stock/",v.stock,name="stock"),
 path("sales/new/",v.sale_new,name="sale_new"),path("sales/",v.bills,name="bills"),
 path("sales/<int:pk>/",v.bill_detail,name="bill"),path("sales/<int:pk>/payment/",v.payment_add,name="payment_add"),
 path("sales/<int:pk>/cancel/",v.cancel_bill,name="cancel_bill"),
 path("receipts/<int:pk>/",v.receipt,name="receipt"),path("receipts/<int:pk>/cancel/",v.cancel_payment,name="cancel_payment")
]
