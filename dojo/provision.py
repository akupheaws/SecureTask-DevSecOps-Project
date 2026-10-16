"""Run inside the Dojo uwsgi container. Set up scoped tests and an API-only account."""

import os, json, pathlib, datetime, secrets

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")
import django

django.setup()
from django.contrib.auth import get_user_model
from dojo.models import Product_Type, Product, Engagement, Test, Test_Type
from rest_framework.authtoken.models import Token

User = get_user_model()
user, _ = User.objects.get_or_create(
    username="securetask-ci",
    defaults={"is_staff": True, "is_superuser": False, "is_active": True},
)
user.set_unusable_password()
user.save()
# Product membership grants imports on this project without superuser access.
from dojo.models import Product_Member, Role

ptype, _ = Product_Type.objects.get_or_create(name="Tutorial Applications")
product, _ = Product.objects.get_or_create(
    name="Secure Task By Akuphe",
    defaults={"description": "AWS DevSecOps tutorial", "prod_type": ptype},
)
role = (
    Role.objects.filter(name="Maintainer").first()
    or Role.objects.filter(name="Owner").first()
)
if role is None:
    raise RuntimeError("Required DefectDojo role not found")
Product_Member.objects.get_or_create(
    product=product, user=user, defaults={"role": role}
)
testtype, _ = Test_Type.objects.get_or_create(name="Generic Findings Import")
result = {}
for scope in ["main", "remediation", "image", "runtime", "demo", "infrastructure"]:
    engagement, _ = Engagement.objects.get_or_create(
        product=product,
        name="Secure Task By Akuphe " + scope,
        defaults={
            "target_start": datetime.date.today(),
            "target_end": datetime.date.today() + datetime.timedelta(days=365),
            "status": "In Progress",
        },
    )
    if scope == "remediation":
        # Keep these exercises independent of earlier optional demo findings.
        engagement.deduplication_on_engagement = True
        engagement.save(update_fields=["deduplication_on_engagement"])
    result[scope] = {}
    tools = {
        "main": ["semgrep", "gitleaks", "osv", "checkov", "hadolint"],
        "remediation": ["semgrep", "gitleaks", "osv", "checkov", "hadolint"],
        "image": ["trivy"],
        "runtime": ["zap"],
        "demo": ["semgrep", "checkov"],
        "infrastructure": ["checkov"],
    }[scope]
    for tool in tools:
        test, _ = Test.objects.get_or_create(
            engagement=engagement,
            title=tool,
            test_type=testtype,
            defaults={
                "target_start": django.utils.timezone.now(),
                "target_end": django.utils.timezone.now(),
            },
        )
        result[scope][tool] = test.id
# Output intended only to a root-owned file, never to logs or CI console.
token, _ = Token.objects.get_or_create(user=user)
path = pathlib.Path("/app/media/securetask-ci.json")
path.write_text(
    json.dumps({"token": token.key, "tests": result, "product_id": product.id})
)
path.chmod(0o600)
print(
    "Secure Task By Akuphe product and scanner tests ready; integration config saved privately."
)
