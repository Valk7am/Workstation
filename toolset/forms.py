from django import forms


class ToolRunForm(forms.Form):
    input_text = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 6}))
    input_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'accept': '.msg'})
    )
