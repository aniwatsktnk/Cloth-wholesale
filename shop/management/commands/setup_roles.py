from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group,Permission
class Command(BaseCommand):
    help="Create staff groups without changing existing users"
    def handle(self,*args,**kwargs):
        roles={"ฝ่ายขาย":["add_bill","add_customer","add_payment"],"สต๊อก":["adjust_stock","add_product"],"ผู้จัดการ":["add_bill","add_customer","add_payment","adjust_stock","add_product","change_bill","change_payment","change_shopsettings","change_product","change_customer"]}
        for name,codes in roles.items():
            group,_=Group.objects.get_or_create(name=name)
            group.permissions.add(*Permission.objects.filter(content_type__app_label="shop",codename__in=codes))
        self.stdout.write(self.style.SUCCESS("พร้อมกำหนดกลุ่มพนักงานในหน้า admin"))
