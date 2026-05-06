from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from .forms import ProfileForm, RegisterForm, UserUpdateForm
from .models import Profile
from toolset.models import ToolActivity
from toolset.activity_helpers import cleanup_expired_downloads


def register_view(request):
	if request.user.is_authenticated:
		return redirect('toolset:dashboard')

	if request.method == 'POST':
		form = RegisterForm(request.POST)
		if form.is_valid():
			user = form.save()
			login(request, user)
			return redirect('toolset:dashboard')
	else:
		form = RegisterForm()

	return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile_view(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	active_tab = request.GET.get('tab', 'profile')

	user_form = UserUpdateForm(instance=request.user)
	profile_form = ProfileForm(instance=profile)

	if request.method == 'POST':
		user_form = UserUpdateForm(request.POST, instance=request.user)
		profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
		if user_form.is_valid() and profile_form.is_valid():
			user_form.save()
			profile_form.save()
			return redirect(request.path + '?tab=profile')
		else:
			active_tab = 'profile'

	activity_qs = ToolActivity.objects.filter(user=request.user).order_by('-created_at')
	cleanup_expired_downloads(user=request.user)
	activity_search = request.GET.get('aq', '').strip()
	if activity_search:
		activity_qs = activity_qs.filter(
			input_text__icontains=activity_search
		) | ToolActivity.objects.filter(
			user=request.user, task_label__icontains=activity_search
		).order_by('-created_at')

	paginator = Paginator(activity_qs, 20)
	page_number = request.GET.get('page', 1)
	page_obj = paginator.get_page(page_number)

	context = {
		'user_form': user_form,
		'profile_form': profile_form,
		'active_tab': active_tab,
		'page_obj': page_obj,
		'activity_search': activity_search,
	}
	return render(request, 'accounts/profile.html', context)
