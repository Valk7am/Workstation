from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import Tool, ToolActivity


DOWNLOAD_TASK_TYPES = {
    Tool.TASK_YOUTUBE_DOWNLOAD,
    Tool.TASK_INSTAGRAM_DOWNLOAD,
    Tool.TASK_FACEBOOK_DOWNLOAD,
    Tool.TASK_TIKTOK_DOWNLOAD,
    Tool.TASK_SOUNDCLOUD_DOWNLOAD,
    Tool.TASK_TWITTER_DOWNLOAD,
}


def is_async_download_task(task_type):
    return task_type in DOWNLOAD_TASK_TYPES


def get_download_ttl_hours():
    return max(1, int(getattr(settings, 'DOWNLOAD_RETENTION_HOURS', 24)))


def build_expires_at():
    return timezone.now() + timedelta(hours=get_download_ttl_hours())


def cleanup_expired_downloads(user=None):
    now = timezone.now()
    qs = ToolActivity.objects.filter(
        status=ToolActivity.STATUS_COMPLETED,
        expires_at__isnull=False,
        expires_at__lte=now,
    )
    if user is not None:
        qs = qs.filter(user=user)

    downloads_root = (Path(settings.BASE_DIR) / 'downloads').resolve()
    cleaned = 0

    for activity in qs:
        result_files = activity.result_files if isinstance(activity.result_files, list) else []

        for file_info in result_files:
            relative_path = file_info.get('relative_path') if isinstance(file_info, dict) else None
            if not relative_path:
                continue

            target = (downloads_root / relative_path).resolve()
            if not str(target).startswith(str(downloads_root)):
                continue

            if target.exists() and target.is_file():
                target.unlink()

        # Keep visible history metadata, but remove direct downloadable paths.
        compact_files = []
        for file_info in result_files:
            if not isinstance(file_info, dict):
                continue
            compact_files.append({
                'name': file_info.get('name') or 'File',
                'size': file_info.get('size') or '',
                'expired': True,
            })

        activity.result_files = compact_files
        activity.status = ToolActivity.STATUS_EXPIRED
        if not activity.result_summary:
            activity.result_summary = 'Download expired and removed from server.'
        activity.save(update_fields=['result_files', 'status', 'result_summary'])
        cleaned += 1

    return cleaned
