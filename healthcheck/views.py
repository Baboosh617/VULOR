from django.shortcuts import render

from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError

def health_check(request):
    """Simple endpoint Render uses to check if app is alive"""
    try:
        db_conn = connections['default']
        db_conn.cursor()
        status = "ok"
    except OperationalError:
        status = "db-down"
    
    return JsonResponse({
        'status': status,
        'database': 'connected' if status == "ok" else "disconnected"
    })
