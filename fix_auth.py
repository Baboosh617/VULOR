# Create a fix script
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vulor.settings')  # Change to your project name
django.setup()

from django.db import transaction
from allauth.socialaccount.models import SocialApp, SocialAccount, SocialToken
from django.contrib.sites.models import Site
from django.contrib.auth.models import User

print("=" * 60)
print("COMPLETE AUTHENTICATION RESET SCRIPT")
print("=" * 60)

with transaction.atomic():
    # 1. Delete all social app data
    print("\n1. Deleting SocialAccount data...")
    SocialToken.objects.all().delete()
    print("   ✓ Deleted SocialToken objects")
    
    SocialAccount.objects.all().delete()
    print("   ✓ Deleted SocialAccount objects")
    
    SocialApp.objects.all().delete()
    print("   ✓ Deleted SocialApp objects")
    
    # 2. Reset sites
    print("\n2. Resetting Site configuration...")
    Site.objects.all().delete()
    
    # Create default site
    default_site, created = Site.objects.get_or_create(
        id=1,
        defaults={
            'domain': 'localhost:8000',
            'name': 'localhost'
        }
    )
    
    if not created:
        default_site.domain = 'localhost:8000'
        default_site.name = 'localhost'
        default_site.save()
    
    print(f"   ✓ Site set to: {default_site} (ID: {default_site.id})")
    
    # 3. Create a test Google app (DISABLED for now)
    print("\n3. Creating Google SocialApp (DISABLED - comment to enable)")
    '''
    # UNCOMMENT THIS SECTION AFTER WE FIX THE TEMPLATE ISSUE
    google_app = SocialApp.objects.create(
        provider='google',
        name='Google OAuth',
        client_id='your-client-id-here.apps.googleusercontent.com',  # Replace
        secret='your-secret-here',  # Replace
    )
    google_app.sites.add(default_site)
    google_app.save()
    print(f"   ✓ Created Google app: {google_app}")
    '''
    
    print("\n" + "=" * 60)
    print("RESET COMPLETE!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Your template should now work without Google button")
    print("2. Test at: http://localhost:8000/signup/")
    print("3. Add Google OAuth later when needed")


