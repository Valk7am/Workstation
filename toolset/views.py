from pathlib import Path
import base64
import io
import mimetypes
import os
import threading
import tempfile

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ToolRunForm
from .models import Tool, ToolActivity
from .activity_helpers import build_expires_at, cleanup_expired_downloads, is_async_download_task


AVAILABLE_TOOLS = [
	{
		'task_type': Tool.TASK_WORD_COUNT,
		'name': 'Word Counter',
		'description': 'Counts words in your input text.',
		'category': 'Text Utilities',
		'icon': 'word-count',
		'keywords': ['word', 'count', 'text', 'counter'],
	},
	{
		'task_type': Tool.TASK_REVERSE_TEXT,
		'name': 'Text Reverser',
		'description': 'Reverses any text you paste.',
		'category': 'Text Utilities',
		'icon': 'reverse-text',
		'keywords': ['reverse', 'text', 'string'],
	},
	{
		'task_type': Tool.TASK_YOUTUBE_DOWNLOAD,
		'name': 'YouTube Downloader',
		'description': 'Downloads a YouTube video using yt-dlp.',
		'category': 'Media',
		'icon': 'youtube',
		'keywords': ['youtube', 'video', 'download', 'yt-dlp'],
	},
	{
		'task_type': Tool.TASK_INSTAGRAM_DOWNLOAD,
		'name': 'Instagram Downloader',
		'description': 'Downloads Instagram videos or images using yt-dlp.',
		'category': 'Media',
		'icon': 'instagram',
		'keywords': ['instagram', 'reel', 'post', 'photo', 'video', 'download', 'yt-dlp'],
	},
	{
		'task_type': Tool.TASK_FACEBOOK_DOWNLOAD,
		'name': 'Facebook Downloader',
		'description': 'Downloads Facebook videos or images using yt-dlp.',
		'category': 'Media',
		'icon': 'facebook',
		'keywords': ['facebook', 'fb', 'video', 'photo', 'reel', 'download', 'yt-dlp'],
	},
	{
		'task_type': Tool.TASK_TIKTOK_DOWNLOAD,
		'name': 'TikTok Downloader',
		'description': 'Downloads TikTok videos using yt-dlp.',
		'category': 'Media',
		'icon': 'tiktok',
		'keywords': ['tiktok', 'ticktock', 'video', 'download', 'yt-dlp'],
	},
	{
		'task_type': Tool.TASK_SOUNDCLOUD_DOWNLOAD,
		'name': 'SoundCloud Downloader',
		'description': 'Downloads SoundCloud tracks using yt-dlp.',
		'category': 'Media',
		'icon': 'soundcloud',
		'keywords': ['soundcloud', 'track', 'audio', 'music', 'download', 'yt-dlp'],
	},
	{
		'task_type': Tool.TASK_TWITTER_DOWNLOAD,
		'name': 'Twitter/X Downloader',
		'description': 'Downloads videos or images from Twitter and X using yt-dlp.',
		'category': 'Media',
		'icon': 'twitter-x',
		'keywords': ['twitter', 'x', 'tweet', 'video', 'image', 'download', 'yt-dlp'],
	},
	{
		'task_type': Tool.TASK_MSG_READER,
		'name': '.msg Reader',
		'description': 'Extracts sender, subject, date, and body from Outlook .msg files.',
		'category': 'File Utilities',
		'icon': 'msg-reader',
		'keywords': ['msg', 'outlook', 'email', 'reader', 'extract'],
	},
	{
		'task_type': Tool.TASK_IMAGE_EDITOR,
		'name': 'Image Editor',
		'description': 'Crop and rotate images. Supports JPG, PNG, WebP, and more.',
		'category': 'File Utilities',
		'icon': 'image-editor',
		'keywords': ['image', 'crop', 'rotate', 'edit', 'photo', 'jpg', 'png'],
	},
]


def home(request):
	if request.user.is_authenticated:
		return redirect('toolset:dashboard')
	return render(request, 'home.html')


@login_required
def dashboard(request):
	query = request.GET.get('q', '').strip().lower()
	selected_category = request.GET.get('category', 'all')

	category_names = sorted({tool['category'] for tool in AVAILABLE_TOOLS})
	categories = [
		{
			'name': category,
			'slug': slugify_category(category),
		}
		for category in category_names
	]

	filtered_tools = AVAILABLE_TOOLS
	if selected_category != 'all':
		filtered_tools = [
			tool for tool in filtered_tools if slugify_category(tool['category']) == selected_category
		]

	if query:
		filtered_tools = [
			tool
			for tool in filtered_tools
			if query in tool['name'].lower()
			or query in tool['description'].lower()
			or any(query in keyword.lower() for keyword in tool['keywords'])
		]

	grouped = {}
	for tool in filtered_tools:
		grouped.setdefault(tool['category'], []).append(tool)

	grouped_tools = [
		{'name': category, 'tools': grouped[category]}
		for category in sorted(grouped.keys())
	]

	context = {
		'grouped_tools': grouped_tools,
		'categories': categories,
		'selected_category': selected_category,
		'query': request.GET.get('q', ''),
	}
	return render(request, 'toolset/dashboard.html', context)


@login_required
def run_tool(request, task_type):
	tool = get_tool_definition(task_type)
	if not tool:
		raise Http404('Tool not found')

	output = None
	queued = False
	queued_activity_id = None
	form = ToolRunForm(request.POST or None, request.FILES or None)

	if tool['task_type'] == Tool.TASK_YOUTUBE_DOWNLOAD:
		form.fields['input_text'].label = 'YouTube URL'
		form.fields['input_text'].help_text = 'Example: https://www.youtube.com/watch?v=...'
		form.fields['input_text'].required = True

	if tool['task_type'] == Tool.TASK_INSTAGRAM_DOWNLOAD:
		form.fields['input_text'].label = 'Instagram URL'
		form.fields['input_text'].help_text = 'Example: https://www.instagram.com/reel/... or /p/...'
		form.fields['input_text'].required = True

	if tool['task_type'] == Tool.TASK_FACEBOOK_DOWNLOAD:
		form.fields['input_text'].label = 'Facebook URL'
		form.fields['input_text'].help_text = 'Example: https://www.facebook.com/... or https://fb.watch/...'
		form.fields['input_text'].required = True

	if tool['task_type'] == Tool.TASK_TIKTOK_DOWNLOAD:
		form.fields['input_text'].label = 'TikTok URL'
		form.fields['input_text'].help_text = 'Example: https://www.tiktok.com/@user/video/...'
		form.fields['input_text'].required = True

	if tool['task_type'] == Tool.TASK_SOUNDCLOUD_DOWNLOAD:
		form.fields['input_text'].label = 'SoundCloud URL'
		form.fields['input_text'].help_text = 'Example: https://soundcloud.com/artist/track or https://on.soundcloud.com/...'
		form.fields['input_text'].required = True

	if tool['task_type'] == Tool.TASK_TWITTER_DOWNLOAD:
		form.fields['input_text'].label = 'Twitter/X URL'
		form.fields['input_text'].help_text = 'Example: https://x.com/.../status/... or https://twitter.com/.../status/...'
		form.fields['input_text'].required = True

	if tool['task_type'] == Tool.TASK_MSG_READER:
		form.fields['input_file'].label = '.msg File'
		form.fields['input_file'].help_text = 'Upload a Microsoft Outlook .msg file.'
		form.fields['input_file'].required = True

	if tool['task_type'] in [Tool.TASK_WORD_COUNT, Tool.TASK_REVERSE_TEXT]:
		form.fields['input_text'].required = True

	if request.method == 'POST':
		if form.is_valid():
			input_text = form.cleaned_data['input_text']
			input_file = form.cleaned_data.get('input_file')

			if is_async_download_task(tool['task_type']):
				activity = ToolActivity.objects.create(
					user=request.user,
					task_type=tool['task_type'],
					task_label=tool['name'],
					input_text=input_text,
					result_summary='Queued. Download is starting...',
					status=ToolActivity.STATUS_IN_PROGRESS,
				)

				thread = threading.Thread(
					target=process_activity_download,
					args=(activity.id, input_text),
					daemon=True,
				)
				thread.start()
				queued = True
				queued_activity_id = activity.id

			if not queued:
				output = execute_tool(tool['task_type'], input_text, input_file)
				log_activity(request.user, tool, input_text, input_file, output)

	context = {
		'tool': tool,
		'form': form,
		'output': output,
		'queued': queued,
		'queued_activity_id': queued_activity_id,
	}
	return render(request, 'toolset/tool_run.html', context)


@login_required
def download_file(request, relative_path):
	cleanup_expired_downloads(user=request.user)

	downloads_root = (Path(settings.BASE_DIR) / 'downloads').resolve()
	target = (downloads_root / relative_path).resolve()

	if not str(target).startswith(str(downloads_root)):
		raise Http404('Invalid download path')

	if not target.exists() or not target.is_file():
		raise Http404('File not found')

	return FileResponse(open(target, 'rb'), as_attachment=True, filename=target.name)


@login_required
def activity_status(request):
	cleanup_expired_downloads(user=request.user)
	activities = ToolActivity.objects.filter(user=request.user).order_by('-created_at')[:5]

	payload = []
	for activity in activities:
		payload.append({
			'id': activity.id,
			'task_label': activity.task_label,
			'status': activity.status,
			'summary': activity.result_summary[:120] if activity.result_summary else '',
			'downloads': activity.result_files if isinstance(activity.result_files, list) else [],
			'created_at': timezone.localtime(activity.created_at).strftime('%b %d, %H:%M'),
			'expires_at': timezone.localtime(activity.expires_at).strftime('%b %d, %H:%M') if activity.expires_at else '',
		})

	in_progress_count = ToolActivity.objects.filter(
		user=request.user,
		status=ToolActivity.STATUS_IN_PROGRESS,
	).count()

	return JsonResponse({
		'in_progress_count': in_progress_count,
		'items': payload,
	})


def execute_tool(task_type, input_text, input_file=None):
	if task_type == Tool.TASK_WORD_COUNT:
		count = len(input_text.split())
		return f"Word count: {count}"

	if task_type == Tool.TASK_REVERSE_TEXT:
		return input_text[::-1]

	if task_type == Tool.TASK_YOUTUBE_DOWNLOAD:
		return download_youtube_video(input_text)

	if task_type == Tool.TASK_INSTAGRAM_DOWNLOAD:
		return download_instagram_media(input_text)

	if task_type == Tool.TASK_FACEBOOK_DOWNLOAD:
		return download_facebook_media(input_text)

	if task_type == Tool.TASK_TIKTOK_DOWNLOAD:
		return download_tiktok_media(input_text)

	if task_type == Tool.TASK_SOUNDCLOUD_DOWNLOAD:
		return download_soundcloud_media(input_text)

	if task_type == Tool.TASK_TWITTER_DOWNLOAD:
		return download_twitter_media(input_text)

	if task_type == Tool.TASK_MSG_READER:
		return read_msg_file(input_file)

	return 'Unsupported tool type.'


def download_youtube_video(url):
	url = url.strip()
	if not (url.startswith('http://') or url.startswith('https://')):
		return 'Please provide a valid YouTube URL starting with http:// or https://'

	try:
		import yt_dlp
	except ImportError:
		return 'yt-dlp is not installed. Install it with: pip install yt-dlp'

	download_dir = Path(settings.BASE_DIR) / 'downloads'
	download_dir.mkdir(parents=True, exist_ok=True)

	options = {
		'format': 'bv*+ba/b',
		'merge_output_format': 'mp4',
		'noplaylist': True,
		'outtmpl': str(download_dir / '%(title)s.%(ext)s'),
		'restrictfilenames': True,
		'quiet': True,
		'no_warnings': True,
		'postprocessors': [{
			'key': 'FFmpegVideoRemuxer',
			'preferedformat': 'mp4',
		}],
	}

	try:
		with yt_dlp.YoutubeDL(options) as ydl:
			info = ydl.extract_info(url, download=True)
			return build_download_result('YouTube', info, ydl)
	except Exception as exc:
		return f"Download failed: {exc}"


def download_instagram_media(url):
	url = url.strip()
	if not (url.startswith('http://') or url.startswith('https://')):
		return 'Please provide a valid Instagram URL starting with http:// or https://'

	if 'instagram.com' not in url.lower():
		return 'Please provide a valid Instagram URL (instagram.com).'

	try:
		import yt_dlp
	except ImportError:
		return 'yt-dlp is not installed. Install it with: pip install yt-dlp'

	instagram_dir = Path(settings.BASE_DIR) / 'downloads' / 'instagram'
	instagram_dir.mkdir(parents=True, exist_ok=True)

	options = {
		'outtmpl': str(instagram_dir / '%(uploader)s_%(id)s.%(ext)s'),
		'restrictfilenames': True,
		'quiet': True,
		'no_warnings': True,
	}

	try:
		with yt_dlp.YoutubeDL(options) as ydl:
			info = ydl.extract_info(url, download=True)
			return build_download_result('Instagram', info, ydl)
	except Exception as exc:
		return f"Download failed: {exc}"


def download_facebook_media(url):
	url = url.strip()
	if not (url.startswith('http://') or url.startswith('https://')):
		return 'Please provide a valid Facebook URL starting with http:// or https://'

	url_lower = url.lower()
	if 'facebook.com' not in url_lower and 'fb.watch' not in url_lower:
		return 'Please provide a valid Facebook URL (facebook.com or fb.watch).'

	try:
		import yt_dlp
	except ImportError:
		return 'yt-dlp is not installed. Install it with: pip install yt-dlp'

	facebook_dir = Path(settings.BASE_DIR) / 'downloads' / 'facebook'
	facebook_dir.mkdir(parents=True, exist_ok=True)

	options = {
		'outtmpl': str(facebook_dir / '%(uploader)s_%(id)s.%(ext)s'),
		'restrictfilenames': True,
		'quiet': True,
		'no_warnings': True,
	}

	try:
		with yt_dlp.YoutubeDL(options) as ydl:
			info = ydl.extract_info(url, download=True)
			return build_download_result('Facebook', info, ydl)
	except Exception as exc:
		return f"Download failed: {exc}"


def download_tiktok_media(url):
	url = url.strip()
	if not (url.startswith('http://') or url.startswith('https://')):
		return 'Please provide a valid TikTok URL starting with http:// or https://'

	url_lower = url.lower()
	if 'tiktok.com' not in url_lower and 'vm.tiktok.com' not in url_lower and 'vt.tiktok.com' not in url_lower:
		return 'Please provide a valid TikTok URL (tiktok.com, vm.tiktok.com, or vt.tiktok.com).'

	try:
		import yt_dlp
	except ImportError:
		return 'yt-dlp is not installed. Install it with: pip install yt-dlp'

	tiktok_dir = Path(settings.BASE_DIR) / 'downloads' / 'tiktok'
	tiktok_dir.mkdir(parents=True, exist_ok=True)

	options = {
		'outtmpl': str(tiktok_dir / '%(uploader)s_%(id)s.%(ext)s'),
		'restrictfilenames': True,
		'quiet': True,
		'no_warnings': True,
	}

	try:
		with yt_dlp.YoutubeDL(options) as ydl:
			info = ydl.extract_info(url, download=True)
			return build_download_result('TikTok', info, ydl)
	except Exception as exc:
		return f"Download failed: {exc}"


def download_soundcloud_media(url):
	url = url.strip()
	if not (url.startswith('http://') or url.startswith('https://')):
		return 'Please provide a valid SoundCloud URL starting with http:// or https://'

	url_lower = url.lower()
	if 'soundcloud.com' not in url_lower and 'on.soundcloud.com' not in url_lower:
		return 'Please provide a valid SoundCloud URL (soundcloud.com or on.soundcloud.com).'

	try:
		import yt_dlp
	except ImportError:
		return 'yt-dlp is not installed. Install it with: pip install yt-dlp'

	soundcloud_dir = Path(settings.BASE_DIR) / 'downloads' / 'soundcloud'
	soundcloud_dir.mkdir(parents=True, exist_ok=True)

	options = {
		'outtmpl': str(soundcloud_dir / '%(uploader)s_%(title)s.%(ext)s'),
		'restrictfilenames': True,
		'quiet': True,
		'no_warnings': True,
	}

	try:
		with yt_dlp.YoutubeDL(options) as ydl:
			info = ydl.extract_info(url, download=True)
			return build_download_result('SoundCloud', info, ydl)
	except Exception as exc:
		return f"Download failed: {exc}"


def download_twitter_media(url):
	url = url.strip()
	if not (url.startswith('http://') or url.startswith('https://')):
		return 'Please provide a valid Twitter/X URL starting with http:// or https://'

	url_lower = url.lower()
	valid_hosts = ('twitter.com', 'x.com', 'mobile.twitter.com', 'mobile.x.com')
	if not any(host in url_lower for host in valid_hosts):
		return 'Please provide a valid Twitter/X URL (twitter.com or x.com).'

	try:
		import yt_dlp
	except ImportError:
		return 'yt-dlp is not installed. Install it with: pip install yt-dlp'

	twitter_dir = Path(settings.BASE_DIR) / 'downloads' / 'twitter'
	twitter_dir.mkdir(parents=True, exist_ok=True)

	options = {
		'outtmpl': str(twitter_dir / '%(uploader)s_%(id)s.%(ext)s'),
		'restrictfilenames': True,
		'quiet': True,
		'no_warnings': True,
	}

	try:
		with yt_dlp.YoutubeDL(options) as ydl:
			info = ydl.extract_info(url, download=True)
			return build_download_result('Twitter/X', info, ydl)
	except Exception as exc:
		return f"Download failed: {exc}"


def read_msg_file(uploaded_file):
	if not uploaded_file:
		return 'Please upload a .msg file.'

	if not uploaded_file.name.lower().endswith('.msg'):
		return 'Invalid file type. Please upload a .msg file.'

	try:
		import extract_msg
	except ImportError:
		return 'extract-msg is not installed. Install it with: pip install extract-msg'

	temp_path = None
	try:
		with tempfile.NamedTemporaryFile(delete=False, suffix='.msg') as temp_file:
			for chunk in uploaded_file.chunks():
				temp_file.write(chunk)
			temp_path = temp_file.name

		msg = extract_msg.Message(temp_path)
		subject = (msg.subject or '').strip()
		sender = (msg.sender or '').strip()
		date = str(msg.date or '').strip()
		to = (getattr(msg, 'to', '') or '').strip()
		cc = (getattr(msg, 'cc', '') or '').strip()
		bcc = (getattr(msg, 'bcc', '') or '').strip()
		body = (msg.body or '').strip()
		html_body = get_html_body(msg)
		attachments = []
		for attachment in getattr(msg, 'attachments', []):
			name = (
				getattr(attachment, 'longFilename', None)
				or getattr(attachment, 'name', None)
				or 'Unnamed attachment'
			)
			data = getattr(attachment, 'data', None)
			size = len(data) if isinstance(data, (bytes, bytearray)) else None
			is_image = is_image_attachment(name)
			attachments.append({
				'name': name,
				'content_id': getattr(attachment, 'contentId', None) or getattr(attachment, 'cid', None) or '',
				'size': format_file_size(size) if size is not None else 'Unknown size',
				'is_image': is_image,
				'image_data_url': build_image_data_url(name, data) if is_image else '',
			})

		if len(body) > 5000:
			body = body[:5000] + '\n\n[Body truncated to 5000 characters]'

		return {
			'subject': subject or 'N/A',
			'sender': sender or 'N/A',
			'date': date or 'N/A',
			'to': to or 'N/A',
			'cc': cc or 'N/A',
			'bcc': bcc or 'N/A',
			'body': body or 'N/A',
			'html_body': html_body,
			'attachments': attachments,
			'attachment_count': len(attachments),
			'file_name': uploaded_file.name,
		}
	except Exception as exc:
		return f"Failed to read .msg file: {exc}"
	finally:
		if temp_path and os.path.exists(temp_path):
			os.remove(temp_path)


def format_file_size(size):
	units = ['B', 'KB', 'MB', 'GB']
	value = float(size)
	for unit in units:
		if value < 1024 or unit == units[-1]:
			return f"{value:.0f} {unit}" if unit == 'B' else f"{value:.1f} {unit}"
		value /= 1024


def get_html_body(msg):
	html_body = getattr(msg, 'htmlBody', None)
	if not html_body:
		return ''

	if isinstance(html_body, bytes):
		for encoding in ('utf-8', 'latin-1'):
			try:
				return html_body.decode(encoding)
			except UnicodeDecodeError:
				continue
		return ''

	return str(html_body)


def is_image_attachment(file_name):
	mime_type, _ = mimetypes.guess_type(file_name)
	return bool(mime_type and mime_type.startswith('image/'))


def build_image_data_url(file_name, data):
	if not isinstance(data, (bytes, bytearray)):
		return ''

	max_preview_size = 5 * 1024 * 1024
	if len(data) > max_preview_size:
		return ''

	mime_type, _ = mimetypes.guess_type(file_name)
	if not mime_type:
		mime_type = 'application/octet-stream'

	encoded = base64.b64encode(data).decode('ascii')
	return f"data:{mime_type};base64,{encoded}"


@login_required
def image_editor(request):
	return render(request, 'toolset/image_editor.html')


@login_required
@require_POST
def image_editor_process(request):
	"""Receive image + crop/rotate params, return processed image."""
	from PIL import Image

	upload = request.FILES.get('image')
	if not upload:
		return JsonResponse({'error': 'No image uploaded.'}, status=400)

	# Basic validation: only allow image MIME types
	allowed_types = {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/bmp', 'image/tiff'}
	if upload.content_type not in allowed_types:
		return JsonResponse({'error': 'Unsupported file type.'}, status=400)

	try:
		img = Image.open(upload)
		img.verify()  # Detect corrupt images
	except Exception:
		return JsonResponse({'error': 'Invalid or corrupt image file.'}, status=400)

	# Re-open after verify (verify closes the file)
	upload.seek(0)
	img = Image.open(upload)
	img = img.convert('RGBA') if img.mode in ('RGBA', 'LA') else img.convert('RGB')

	# --- Apply rotation ---
	rotation = int(request.POST.get('rotation', 0)) % 360
	if rotation:
		img = img.rotate(-rotation, expand=True)  # Cropper.js rotation is clockwise

	# --- Apply crop ---
	try:
		crop_x = float(request.POST.get('crop_x', 0))
		crop_y = float(request.POST.get('crop_y', 0))
		crop_w = float(request.POST.get('crop_w', 0))
		crop_h = float(request.POST.get('crop_h', 0))
	except (TypeError, ValueError):
		crop_x = crop_y = crop_w = crop_h = 0

	if crop_w > 0 and crop_h > 0:
		left = max(0, int(crop_x))
		top = max(0, int(crop_y))
		right = min(img.width, int(crop_x + crop_w))
		bottom = min(img.height, int(crop_y + crop_h))
		if right > left and bottom > top:
			img = img.crop((left, top, right, bottom))

	# --- Determine output format ---
	original_name = upload.name or 'image.jpg'
	ext = Path(original_name).suffix.lower()
	fmt_map = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP', '.bmp': 'BMP'}
	fmt = fmt_map.get(ext, 'JPEG')
	output_ext = ext if ext in fmt_map else '.jpg'
	content_type_map = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp', 'BMP': 'image/bmp'}

	# PNG/WebP support transparency; JPEG does not
	if fmt == 'JPEG' and img.mode == 'RGBA':
		background = Image.new('RGB', img.size, (255, 255, 255))
		background.paste(img, mask=img.split()[3])
		img = background

	buf = io.BytesIO()
	save_kwargs = {'format': fmt}
	if fmt == 'JPEG':
		save_kwargs['quality'] = 92
		save_kwargs['optimize'] = True
	img.save(buf, **save_kwargs)
	buf.seek(0)

	output_name = Path(original_name).stem + '_edited' + output_ext
	response = HttpResponse(buf, content_type=content_type_map.get(fmt, 'image/jpeg'))
	response['Content-Disposition'] = f'attachment; filename="{output_name}"'
	return response


def build_download_result(platform, info, ydl):
	downloads = extract_downloaded_files(info, ydl)
	title = (info.get('title') or platform + ' media').strip() if isinstance(info, dict) else f'{platform} media'

	if not downloads:
		return f"Downloaded: {title}\nSaved under: {Path(settings.BASE_DIR) / 'downloads'}"

	return {
		'kind': 'download_result',
		'platform': platform,
		'title': title,
		'count': len(downloads),
		'downloads': downloads,
	}


def extract_downloaded_files(info, ydl):
	downloads_root = (Path(settings.BASE_DIR) / 'downloads').resolve()
	items = []
	if isinstance(info, dict) and info.get('entries'):
		items = [entry for entry in info['entries'] if entry]
	else:
		items = [info]

	found = []
	seen = set()
	for item in items:
		if not isinstance(item, dict):
			continue

		candidate_paths = []
		for requested in item.get('requested_downloads') or []:
			filepath = requested.get('filepath')
			if filepath:
				candidate_paths.append(Path(filepath))

		filename = item.get('_filename')
		if filename:
			candidate_paths.append(Path(filename))

		try:
			candidate_paths.append(Path(ydl.prepare_filename(item)))
		except Exception:
			pass

		resolved = pick_existing_download(candidate_paths)
		if not resolved:
			continue

		resolved = resolved.resolve()
		if not str(resolved).startswith(str(downloads_root)):
			continue

		if str(resolved) in seen:
			continue
		seen.add(str(resolved))

		found.append({
			'name': resolved.name,
			'size': format_file_size(resolved.stat().st_size),
			'relative_path': str(resolved.relative_to(downloads_root)),
		})

	return found


def pick_existing_download(paths):
	for path in paths:
		if path.exists() and path.is_file():
			return path

	for path in paths:
		for suffix in ('.mp4', '.mkv', '.webm', '.m4a', '.jpg', '.jpeg', '.png'):
			variant = path.with_suffix(suffix)
			if variant.exists() and variant.is_file():
				return variant

	return None


def log_activity(user, tool, input_text, input_file, output):
	result_files = []
	result_summary = ''

	if isinstance(output, dict) and output.get('kind') == 'download_result':
		result_files = output.get('downloads', [])
		result_summary = output.get('title', '')
	elif isinstance(output, str):
		result_summary = output[:500]

	input_value = input_text or (input_file.name if input_file else '')

	ToolActivity.objects.create(
		user=user,
		task_type=tool['task_type'],
		task_label=tool['name'],
		input_text=input_value,
		result_summary=result_summary,
		result_files=result_files,
		status=ToolActivity.STATUS_COMPLETED,
		completed_at=timezone.now(),
	)


def process_activity_download(activity_id, input_text):
	try:
		activity = ToolActivity.objects.get(id=activity_id)
	except ToolActivity.DoesNotExist:
		return

	try:
		output = execute_tool(activity.task_type, input_text, None)

		if isinstance(output, dict) and output.get('kind') == 'download_result':
			activity.result_files = output.get('downloads', [])
			activity.result_summary = output.get('title', '') or 'Download completed.'
			activity.status = ToolActivity.STATUS_COMPLETED
			activity.completed_at = timezone.now()
			activity.expires_at = build_expires_at()
			activity.save(update_fields=['result_files', 'result_summary', 'status', 'completed_at', 'expires_at'])
			return

		activity.result_summary = str(output)[:500] if output else 'Download failed.'
		activity.status = ToolActivity.STATUS_FAILED
		activity.completed_at = timezone.now()
		activity.save(update_fields=['result_summary', 'status', 'completed_at'])
	except Exception as exc:
		activity.result_summary = f'Processing failed: {exc}'
		activity.status = ToolActivity.STATUS_FAILED
		activity.completed_at = timezone.now()
		activity.save(update_fields=['result_summary', 'status', 'completed_at'])


def get_tool_definition(task_type):
	for tool in AVAILABLE_TOOLS:
		if tool['task_type'] == task_type:
			return tool
	return None


def slugify_category(category):
	return category.lower().replace(' ', '_')
