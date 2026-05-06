from django.db import models
from django.contrib.auth.models import User


class Tool(models.Model):
	TASK_WORD_COUNT = 'word_count'
	TASK_REVERSE_TEXT = 'reverse_text'
	TASK_YOUTUBE_DOWNLOAD = 'youtube_download'
	TASK_INSTAGRAM_DOWNLOAD = 'instagram_download'
	TASK_FACEBOOK_DOWNLOAD = 'facebook_download'
	TASK_TIKTOK_DOWNLOAD = 'tiktok_download'
	TASK_SOUNDCLOUD_DOWNLOAD = 'soundcloud_download'
	TASK_TWITTER_DOWNLOAD = 'twitter_download'
	TASK_MSG_READER = 'msg_reader'
	TASK_IMAGE_EDITOR = 'image_editor'

	TASK_CHOICES = [
		(TASK_WORD_COUNT, 'Word Counter'),
		(TASK_REVERSE_TEXT, 'Text Reverser'),
		(TASK_YOUTUBE_DOWNLOAD, 'YouTube Downloader (yt-dlp)'),
		(TASK_INSTAGRAM_DOWNLOAD, 'Instagram Downloader (yt-dlp)'),
		(TASK_FACEBOOK_DOWNLOAD, 'Facebook Downloader (yt-dlp)'),
		(TASK_TIKTOK_DOWNLOAD, 'TikTok Downloader (yt-dlp)'),
		(TASK_SOUNDCLOUD_DOWNLOAD, 'SoundCloud Downloader (yt-dlp)'),
		(TASK_TWITTER_DOWNLOAD, 'Twitter/X Downloader (yt-dlp)'),
		(TASK_MSG_READER, '.msg Reader'),
		(TASK_IMAGE_EDITOR, 'Image Editor'),
	]

	owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tools')
	name = models.CharField(max_length=100)
	description = models.TextField(blank=True)
	task_type = models.CharField(max_length=32, choices=TASK_CHOICES)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.name


class ToolActivity(models.Model):
	STATUS_IN_PROGRESS = 'in_progress'
	STATUS_COMPLETED = 'completed'
	STATUS_FAILED = 'failed'
	STATUS_EXPIRED = 'expired'

	STATUS_CHOICES = [
		(STATUS_IN_PROGRESS, 'In Progress'),
		(STATUS_COMPLETED, 'Completed'),
		(STATUS_FAILED, 'Failed'),
		(STATUS_EXPIRED, 'Expired'),
	]

	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tool_activities')
	task_type = models.CharField(max_length=32, blank=True)
	task_label = models.CharField(max_length=120, blank=True)
	input_text = models.TextField(blank=True)
	result_summary = models.TextField(blank=True)
	result_files = models.JSONField(default=list, blank=True)
	status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
	completed_at = models.DateTimeField(null=True, blank=True)
	expires_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.user.username} | {self.task_label} | {self.created_at:%Y-%m-%d %H:%M}"
