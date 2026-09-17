from django import forms
from .models import Product,Customer,Payment,ShopSettings,PriceTier,CustomerPrice
class ProductForm(forms.ModelForm):
    class Meta:
        model=Product
        fields=["sku","style","name","color","size","image_url","retail","wholesale","minimum","active"]
    def clean_image_url(self):
        value=self.cleaned_data["image_url"]
        if value and not value.startswith("https://"):
            raise forms.ValidationError("ใช้ลิงก์รูปภาพที่ขึ้นต้นด้วย https://")
        return value
class CustomerForm(forms.ModelForm):
    credit_days=forms.IntegerField(label="เครดิต (วัน)",min_value=0,max_value=365,initial=0)
    class Meta: model=Customer;fields=["name","phone","address","tax_id","credit_days"]
class SettingsForm(forms.ModelForm):
    class Meta: model=ShopSettings;fields=["name","address","tax_id","phone"]
class SaleForm(forms.Form):
    key=forms.UUIDField(widget=forms.HiddenInput)
    customer=forms.ModelChoiceField(label="ลูกค้า (จำเป็นเมื่อมีเงินค้าง)",queryset=Customer.objects.all(),required=False)
    discount=forms.DecimalField(label="ส่วนลดท้ายบิล",min_value=0,decimal_places=2,max_digits=12,initial=0)
    paid=forms.DecimalField(label="ยอดที่รับเงินจริงครั้งนี้",min_value=0,decimal_places=2,max_digits=12,initial=0)
    method=forms.ChoiceField(label="วิธีรับเงิน",choices=Payment.METHODS)
    reference=forms.CharField(label="เลขอ้างอิงการชำระ",max_length=160,required=False)
    due_date=forms.DateField(label="ครบกำหนดชำระ (เว้นว่างเพื่อใช้เครดิตลูกค้า)",required=False,widget=forms.DateInput(attrs={"type":"date"}))
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

Tiers=forms.inlineformset_factory(Product,PriceTier,fields=["minimum_quantity","price"],extra=1,can_delete=True,max_num=20,validate_max=True)
SpecialPrices=forms.inlineformset_factory(Product,CustomerPrice,fields=["customer","price"],extra=1,can_delete=True,max_num=200,validate_max=True)

class DueDateForm(forms.Form):
    due_date=forms.DateField(label="วันครบกำหนดใหม่",widget=forms.DateInput(attrs={"type":"date"}))
    reason=forms.CharField(label="เหตุผลที่แก้ไข",max_length=300)

class ReceiptFilterForm(forms.Form):
    customer=forms.ModelChoiceField(label='ลูกค้า',queryset=Customer.objects.all(),required=False)
    start=forms.DateField(label='ตั้งแต่วันที่',required=False,widget=forms.DateInput(attrs={'type':'date'}))
    end=forms.DateField(label='ถึงวันที่',required=False,widget=forms.DateInput(attrs={'type':'date'}))
    q=forms.CharField(label='เลขใบเสร็จ / เลขบิล / ชื่อลูกค้า',required=False,max_length=160)
    def clean(self):
        data=super().clean()
        if data.get('start') and data.get('end') and data['start']>data['end']:
            raise forms.ValidationError('วันที่เริ่มต้องไม่เกินวันที่สิ้นสุด')
        return data

class BundleForm(forms.Form):
    key=forms.UUIDField(widget=forms.HiddenInput)
    payments=forms.ModelMultipleChoiceField(label='ใบเสร็จ',queryset=Payment.objects.filter(voided=False,bill__status='open'),widget=forms.CheckboxSelectMultiple)

class MoneyReportForm(forms.Form):
    start=forms.DateField(label='ตั้งแต่วันที่',widget=forms.DateInput(attrs={'type':'date'}))
    end=forms.DateField(label='ถึงวันที่',widget=forms.DateInput(attrs={'type':'date'}))
    def clean(self):
        data=super().clean();start=data.get('start');end=data.get('end')
        if start and end and (end<start or (end-start).days>365):
            raise forms.ValidationError('เลือกช่วงวันที่ไม่เกิน 366 วัน และวันสิ้นสุดต้องไม่ก่อนวันเริ่ม')
        return data
