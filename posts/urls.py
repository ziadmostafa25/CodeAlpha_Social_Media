from django.urls import path
from . import views

app_name = 'posts'

urlpatterns = [
    # Feed & Post CRUD
    path('', views.feed_view, name='feed'),
    path('post/<int:post_id>/', views.post_detail_view, name='post_detail'),
    path('post/create/', views.create_post_view, name='create_post'),
    path('post/<int:post_id>/edit/', views.edit_post_view, name='edit_post'),
    path('post/<int:post_id>/delete/', views.delete_post_view, name='delete_post'),
    
    # Interactions: Likes, Comments, Reposts, Saves, Reports
    path('post/<int:post_id>/like/', views.like_toggle_view, name='like_toggle'),
    path('post/<int:post_id>/comment/', views.add_comment_view, name='add_comment'),
    path('comment/<int:comment_id>/delete/', views.delete_comment_view, name='delete_comment'),
    path('post/<int:post_id>/repost/', views.repost_toggle_view, name='repost_toggle'),
    path('post/<int:post_id>/save/', views.save_toggle_view, name='save_toggle'),
    path('post/<int:post_id>/report/', views.report_post_view, name='report_post'),
    path('saved/', views.saved_posts_view, name='saved_posts'),

    # Reels Video Experience
    path('reels/', views.reels_feed_view, name='reels'),
    path('reels/upload/', views.create_reel_view, name='create_reel'),
    path('reels/<int:reel_id>/delete/', views.delete_reel_view, name='delete_reel'),
    path('reels/<int:reel_id>/like/', views.reel_like_toggle_view, name='reel_like'),
    path('reels/<int:reel_id>/save/', views.reel_save_toggle_view, name='reel_save'),
    path('reels/<int:reel_id>/view/', views.record_reel_view, name='reel_view'),
    path('reels/<int:reel_id>/comment/', views.reel_comment_view, name='reel_comment'),
    path('reels/<int:reel_id>/report/', views.report_reel_view, name='report_reel'),
]
