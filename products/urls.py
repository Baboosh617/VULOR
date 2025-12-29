from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('product<slug:slug>/', views.product_detail, name='product_detail'),
    path('review/add/<int:product_id>/', views.add_review, name='add_review'),
]