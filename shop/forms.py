from django import forms
from .models import Product,Customer,Payment,ShopSettings
class ProductForm(forms.ModelForm):
    class Meta:
        model=Product
        fields=["sku","style","name","color","size","retail","wholesale","minimum","active"]
class CustomerForm(forms.ModelForm):
    class Meta: model=Customer;fields=["name","phone","address","tax_id"]
class SettingsForm(forms.ModelForm):
    class Meta: model=ShopSettings;fields=["name","address","tax_id","phone"]
class SaleForm(forms.Form):
    key=forms.UUIDField(widget=forms.HiddenInput)
    customer=forms.ModelChoiceField(label="ลูกค้า (จำเป็นเมื่อมีเงินค้าง)",queryset=Customer.objects.all(),required=False)
    discount=forms.DecimalField(label="ส่วนลดท้ายบิล",min_value=0,decimal_places=2,max_digits=12,initial=0)
    paid=forms.DecimalField(label="ยอดที่รับเงินจริงครั้งนี้",min_value=0,decimal_places=2,max_digits=12,initial=0)
    method=forms.ChoiceField(label="วิธีรับเงิน",choices=Payment.METHODS)
    reference=forms.CharField(label="เลขอ้างอิงการชำระ",max_length=160,required=False)
class ItemForm(forms.Form):
    product=forms.ModelChoiceField(label="สินค้า",queryset=Product.objects.filter(active=True))
    quantity=forms.IntegerField(label="จำนวน",min_value=1,max_value=10000)
Items=forms.formset_factory(ItemForm,extra=1,max_num=100,validate_max=True,can_delete=True)
class ReceiveForm(forms.Form):
    key=forms.UUIDField(widget=forms.HiddenInput)
    value=forms.DecimalField(label="รับชำระเพิ่ม",min_value=.01,decimal_places=2,max_digits=12)
    method=forms.ChoiceField(label="วิธีรับเงิน",choices=Payment.METHODS)
    reference=forms.CharField(label="เลขอ้างอิง",max_length=160,required=False)
class StockForm(forms.Form):
    product=forms.ModelChoiceField(label="สินค้า",queryset=Product.objects.all())
    delta=forms.IntegerField(label="จำนวนเพิ่ม/ลด (ใช้ค่าติดลบเพื่อลด)",min_value=-100000,max_value=100000)
    reason=forms.CharField(label="เหตุผล / เลขที่รับสินค้า",max_length=250)
class ReasonForm(forms.Form):
    reason=forms.CharField(label="เหตุผล (การคืนเงินต้องดำเนินการจริงแยกจากระบบ)",max_length=500,widget=forms.Textarea)
