from django.contrib import admin
from .models import Product,Customer,ShopSettings
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display=["sku","name","color","size","cost","retail","wholesale","stock"]
    search_fields=["sku","name"]
    readonly_fields=["stock"]
admin.site.register(Customer)
@admin.register(ShopSettings)
class ShopAdmin(admin.ModelAdmin):
    def has_add_permission(self,request): return not ShopSettings.objects.exists() and super().has_add_permission(request)
    def has_delete_permission(self,request,obj=None): return False
admin.site.site_header="Cloth Wholesale · ผู้ดูแลระบบ"
